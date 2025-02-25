# -*- coding: utf-8 -*-
u"""
User transformation widgets
---------------------------

If the data pipeline is supposed to take user actions from GUI, each
transformation node should have a dedicated Qt widget that sets relevant
transformation parameters. ParSeq offers the base class :class:`PropWidget`
that reduces the task of creating a widget down to instantiating Qt control
elements, putting them in a Qt layout and registering them. The docstrings of
the user widget class will be built by ParSeq using Sphinx documentation system
into an html file that will be displayed under the corresponding widget window
or in a web browser.

User transformation widgets can profit from using `silx library
<https://www.silx.org/>`_, as ParSeq already uses it heavily. It has many
widgets that are internally integrated to plotting e.g. ROIs. A good first
point of interaction with silx is its collection of examples.
"""
__author__ = "Konstantin Klementiev"
__date__ = "4 May 2024"
# !!! SEE CODERULES.TXT !!!

from functools import partial
from collections import OrderedDict
import reprlib

from silx.gui import qt

from ..core import singletons as csi
from ..core import commons as cco
from ..core import config
from ..core.logger import logger, syslogger
from . import undoredo as gur
from . import propsOfData as gpd

propWidgetTypes = (
    'edit', 'label', 'spinbox', 'groupbox', 'checkbox', 'pushbutton',
    'tableview', 'combobox', 'rangewidget', 'statebuttons', 'correction')

spinBoxDelay = 100  # ms


class FloatRepr(reprlib.Repr):
    def repr_float(self, value, level):
        return format(value, '.3f')

    def repr_float64(self, value, level):
        return self.repr_float(value, level)


class QLineEditSelectRB(qt.QLineEdit):
    def __init__(self, parent=None, rb=None):
        super().__init__(parent)
        self.buddyRB = rb

    def focusInEvent(self, e):
        self.buddyRB.setChecked(True)
        super().focusInEvent(e)


# #  to replace the standard stepBy method of a SpinBox without inheritance:
# def stepByWithUpdate(self, oldStepBy, parent, dataItems, key, steps):
#     oldStepBy(steps)
#     self.setEnabled(False)  # to prevent double acting
#     parent.updateProp(key, self.value(), dataItems)
#     self.setEnabled(True)


class PropWidget(qt.QWidget):
    u"""The base class for user transformation widgets and a few internal
    ParSeq widgets. The main idea of this class is to automatize a number of
    tasks: setting GUI from data, changing transformation parameters of data
    from GUI, copying parameters to other data, starting transformation and
    inserting user changes into undo and redo lists.
    """

    # this dict is designed to hold widget-related properties, not data-related
    # ones (the latter are stored in data.transformParams).
    properties = dict()
    extraLines = []
    plotParams = {}
    LOCATION = 'transform'  # 'transform' or 'correction'

    def __init__(self, parent=None, node=None):
        u"""*node* is the corresponding transformation node, instance of
        :class:`.Node`. This parental __init__() must be invoked in the derived
        classes at the top of their __init__() constructors. In the constructor
        of the derived class, the user should create control elements and
        register them by using the methods listed below.
        """
        super().__init__(parent)
        self.node = node
        self.hideInitialView = False
        self.shouldRemoveNonesFromProps = False

        self.propWidgets = OrderedDict()
        self.propGroups = OrderedDict()
        self.exclusivePropGroups = OrderedDict()
        self.statusWidgets = OrderedDict()
        # self.setContextMenuPolicy(qt.Qt.CustomContextMenu)
        # self.setContextMenuPolicy(qt.Qt.DefaultContextMenu)
        # self.customContextMenuRequested.connect(self.onCustomContextMenu)

        self.spinTimer = qt.QTimer(self)
        self.spinTimer.setSingleShot(True)
        self.spinTimer.timeout.connect(self.spinDelayed)
        self.spinBoxProps = None

        self.read_ini_properties()

        if csi.tasker is not None:
            csi.tasker.ready.connect(self._onTransformThreadReady)

    def read_ini_properties(self):
        sec = self.__class__.__name__
        if config.configTransforms.has_section(sec):
            for key in self.properties:
                try:
                    testStr = config.configTransforms.get(sec, key)
                except Exception:
                    continue
                try:
                    self.properties[key] = eval(testStr)
                except (SyntaxError, NameError):
                    self.properties[key] = testStr
            if len(self.plotParams) > 0:
                try:
                    testStr = config.configTransforms.get(sec, 'plotParams')
                except Exception:
                    return
                try:
                    self.plotParams.update(eval(testStr))
                except (SyntaxError, NameError):
                    return

    def _addAction(self, menu, text, slot, shortcut=None):
        action = qt.QAction(text, self)
        if text.startswith('apply'):
            icon = self.style().standardIcon(qt.QStyle.SP_DialogApplyButton)
        elif text.startswith('reset'):
            icon = self.style().standardIcon(qt.QStyle.SP_DialogCancelButton)
        else:
            icon = None
        if icon is not None:
            action.setIcon(icon)
        action.triggered.connect(slot)
        if shortcut:
            action.setShortcut(qt.QKeySequence(shortcut))
        action.setShortcutContext(qt.Qt.WidgetWithChildrenShortcut)
        menu.addAction(action)
        return action

    def _widgetsAt(self, pos):
        """Discover widgets under the cursor. The topmost comes first."""
        widgets, attrs = [], []
        widgetAt = qt.qApp.widgetAt(pos)

        while widgetAt:
            widgets.append(widgetAt)
            # Make widget invisible to further enquiries
            attr = widgetAt.testAttribute(qt.Qt.WA_TransparentForMouseEvents)
            attrs.append(attr)
            if not attr:
                widgetAt.setAttribute(qt.Qt.WA_TransparentForMouseEvents)
            widgetAt = qt.qApp.widgetAt(pos)

        # Restore attribute
        for widget, attr in zip(widgets, attrs):
            widget.setAttribute(qt.Qt.WA_TransparentForMouseEvents, attr)

        return widgets

    # def onCustomContextMenu(self, point):
    def contextMenuEvent(self, event):
        if not self.propWidgets:
            return
        widgetsOver = self._widgetsAt(event.globalPos())
        out = [w in self.propWidgets or w in self.propGroups or
               w in self.exclusivePropGroups for w in widgetsOver]
        if sum(out) == 0:
            return
        tNames = [self.propWidgets[w]['transformNames'] for w in widgetsOver
                  if w in self.propWidgets]
        menu = qt.QMenu(self)
        self.fillMenuApply(widgetsOver, menu)
        if len(tNames) > 0:
            menu.addSeparator()
            self.fillMenuReset(widgetsOver, menu)

        hdf5Path = None
        for widget in widgetsOver:
            if hasattr(widget, 'text'):
                try:
                    txt = widget.text()
                    if txt.startswith('silx:'):
                        hdf5Path = txt
                except Exception:
                    pass
        if hdf5Path:
            menu.addSeparator()
            self._addAction(menu, "go to hdf5 location",
                            partial(self.gotoHDF5, hdf5Path))

        for w in widgetsOver:  # editingFinished is emitted before menu.exec_
            w.blockSignals(True)
        menu.exec_(event.globalPos())
        for w in widgetsOver:
            w.blockSignals(False)

    def fillMenuApply(self, widgetsOver, menu):
        if len(csi.selectedItems) == 0:
            return
        actionStr = 'apply {0}{1}'
        data = csi.selectedItems[0]

        tNames = []
        for widget in widgetsOver:
            if not widget.isEnabled():
                continue
            res = None
            if widget in self.propGroups:
                props = self._getPropListGroup(widget)
                if props is None:  # when a widget in the group is disabled
                    continue
                cap = self.propGroups[widget]['caption']
            elif widget in self.propWidgets:
                propWidget = self.propWidgets[widget]
                tNames = list(propWidget['transformNames'])
                tNames += [tr.name for tr in self.node.transformsOut]
                props = self._getPropListWidget(widget)
                if 'copyValue' in propWidget:
                    res = propWidget['copyValue']
                    if not isinstance(res, (list, tuple)):
                        res = [res]
                    values = [
                        cco.getDotAttr(data, prop) if v == 'from data' else v
                        for prop, v in zip(props, res)]
                cap = propWidget['caption']
            elif widget in self.exclusivePropGroups:
                props = self._getPropListExclusiveGroup(widget)
                cap = self.exclusivePropGroups[widget]['caption']
            else:
                continue
            if res is None:  # if not 'copyValue' in propWidget
                values = [cco.getDotAttr(data, prop) for prop in props]

            if len(values) == 1:
                curValue = values[0]
                if isinstance(curValue, float):
                    valueStr = ' = {0:g}'.format(curValue)
                else:
                    valueStr = ' = {0}'.format(FloatRepr().repr(curValue))
                # if widget in self.propWidgets:
                #     propWidget = self.propWidgets[widget]
                #     if propWidget['widgetTypeIndex'] == 0:  # edit
                #         if curValue:
                #             if curValue.startswith('silx:'):
                #                 hdf5Path = curValue
            else:
                valueStr = ''
            actionName = actionStr.format(cap, valueStr)
            actionName2 = actionName + ' to picked data'
            self._addAction(
                menu, actionName2,
                partial(self.startPick, props, values, actionName))
            syslogger.info('widget in widgetsOver:')
            syslogger.info(f'actionName is {actionName}')
            syslogger.info(f'props = {props}')
            syslogger.info(f'values = {values}')

        if len(tNames) == 0:
            return
        if props is None:
            return

        for tName in tNames:
            tr = csi.transforms[tName]
            validProps = []
            for prop in props:
                key = cco.shrinkTransformParam(prop)
                if key in tr.defaultParams:
                    validProps.append(prop)
            if len(validProps) == 0:
                continue

            keys = tr.defaultParams.keys()
            allDefProps = [cco.expandTransformParam(key) for key in keys]
            allDefValues = [data.transformParams[key] for key in keys]
            actionName = 'apply all params of "{0}"'.format(tName)
            actionName2 = actionName + ' to picked data'
            self._addAction(
                menu, actionName2,
                partial(self.startPick, allDefProps, allDefValues, actionName))
            syslogger.info('apply all params of the transform')
            syslogger.info(f'actionName = {actionName}')
            syslogger.info(f'allDEfProps = {allDefProps}')
            syslogger.info(f'allDefValues = {allDefValues}')

        allProps = [cco.expandTransformParam(key)
                    for key in data.transformParams.keys()]
        allValues = list(data.transformParams.values())
        actionName = 'apply all params of all transforms'
        actionName2 = actionName + ' to picked data'
        self._addAction(
            menu, actionName2,
            partial(self.startPick, allProps, allValues, actionName))
        syslogger.info('apply all params of all transforms')
        syslogger.info(f'actionName: {actionName}')
        syslogger.info(f'allProps = {allProps}')
        syslogger.info(f'allValues = {allValues}')

    def fillMenuReset(self, widgetsOver, menu):
        actionStr = 'reset {0} to default value{1}'

        tr = None
        for widget in widgetsOver:
            tNames = []
            if not widget.isEnabled():
                continue
            if widget in self.propGroups:
                props = self._getPropListGroup(widget)
                if props is None:  # when a widget in the group is disabled
                    continue
                cap = self.propGroups[widget]['caption']
            elif widget in self.propWidgets:
                props = self._getPropListWidget(widget)
                cap = self.propWidgets[widget]['caption']
                tNames = list(self.propWidgets[widget]['transformNames'])
                tNames += [tr.name for tr in self.node.transformsOut]
            elif widget in self.exclusivePropGroups:
                props = self._getPropListExclusiveGroup(widget)
                cap = self.exclusivePropGroups[widget]['caption']
            else:
                continue
            values, validProps = [], []
            for tName in tNames:
                if tName is None:
                    continue
                tr = csi.transforms[tName]
                for prop in props:
                    key = cco.shrinkTransformParam(prop)
                    if key in tr.defaultParams:
                        defVal = tr.defaultParams[key]
                        values.append(defVal)
                        validProps.append(prop)

            if len(values) == 0:
                continue
            elif len(values) == 1:
                curValue = values[0]
                if isinstance(curValue, float):
                    valueStr = ' {0:g}'.format(curValue)
                else:
                    valueStr = ' {0}'.format(curValue)
            else:
                valueStr = 's'
            actionName = actionStr.format(cap, valueStr)
            self._addAction(
                menu, actionName,
                partial(self.resetProps, validProps, values, actionName))

        if tr is None:
            return
        keys = tr.defaultParams.keys()
        props = [cco.expandTransformParam(key) for key in keys]
        values = list(tr.defaultParams.values())
        actionName = 'reset all params of "{0}" to default values'\
            .format(tr.name)
        self._addAction(menu, actionName,
                        partial(self.resetProps, props, values, actionName))

        props, values = [], []
        for transform in csi.transforms.values():
            for key in transform.defaultParams.keys():
                props.append(cco.expandTransformParam(key))
                values.append(transform.defaultParams[key])
        actionName = 'reset all params of all transforms to default values'
        self._addAction(menu, actionName,
                        partial(self.resetProps, props, values, actionName))

    def _getPropListWidget(self, widget):
        propWidget = self.propWidgets[widget]
        res = propWidget['prop']
        return res if isinstance(res, (list, tuple)) else [res]

    def _getPropListGroup(self, widget):
        res = []
        for w in self.propGroups[widget]['widgets']:
            if not w.isEnabled():
                return
            if w in self.propWidgets:
                res.extend(self._getPropListWidget(w))
            elif w in self.exclusivePropGroups:
                res.extend(self._getPropListExclusiveGroup(w))
        return res

    def _getPropListExclusiveGroup(self, widget):
        dd = self.exclusivePropGroups[widget]
        if 'props' in dd:  # rbuttons with edits
            res = dd['props']
        elif 'prop' in dd:  # only rbuttons
            res = dd['prop']
        else:
            return []
        return res if isinstance(res, (list, tuple)) else [res]

    def startPick(self, props, values, actionName):
        self.pendingProps = props
        self.pendingValues = values
        self.pendingActionName = actionName
        syslogger.info('startPick')
        syslogger.info(f'pendingActionName: {self.pendingActionName}')
        syslogger.info(f'pendingProps = {self.pendingProps}')
        syslogger.info(f'pendingValues = {self.pendingValues}')
        if self.node is not None:  # can be True with tests
            self.node.widget.preparePickData(self)

    def applyPendingProps(self):
        syslogger.info('applyPendingProps')
        syslogger.info(f'pendingActionName: {self.pendingActionName}')
        syslogger.info(f'pendingProps = {self.pendingProps}')
        syslogger.info(f'pendingValues = {self.pendingValues}')
        dataItems = csi.selectedItems
        gur.pushTransformToUndo(
            self, dataItems, self.pendingProps, self.pendingValues,
            self.pendingActionName)
        nChanged = gpd.copyProps(
            dataItems, self.pendingProps, self.pendingValues,
            self.shouldRemoveNonesFromProps)
        if not nChanged:
            csi.mainWindow.displayStatusMessage('no changes')
            return
        self.updateProp()
        self.setUIFromData()

    def resetProps(self, props, values, actionName):
        dataItems = csi.selectedItems
        gur.pushTransformToUndo(self, dataItems, props, values, actionName)
        nChanged = gpd.copyProps(dataItems, props, values,
                                 self.shouldRemoveNonesFromProps)
        if not nChanged:
            csi.mainWindow.displayStatusMessage('no changes')
            return
        self.updateProp()
        self.setUIFromData()

    def undoProps(self, lastAction):
        _, dataItems, params, prevValues, values, _ = lastAction
        nChanged = 0
        for item, prevs in zip(dataItems, prevValues):
            nChanged += gpd.copyProps(
                [item], params, prevs, self.shouldRemoveNonesFromProps)
        if not nChanged:
            csi.mainWindow.displayStatusMessage('no changes')
            return
        self.updateProp(dataItems=dataItems)
        self.setUIFromData()

    def redoProps(self, lastAction):
        _, dataItems, params, prevValues, values, _ = lastAction
        nChanged = gpd.copyProps(
            dataItems, params, values, self.shouldRemoveNonesFromProps)
        if not nChanged:
            csi.mainWindow.displayStatusMessage('no changes')
            return
        self.updateProp(dataItems=dataItems)
        self.setUIFromData()

    def gotoHDF5(self, path):
        if self.node is None:  # can be True with tests
            return
        self.node.widget.files.gotoWhenReady(path)

    def changeTooltip(self, edit, txt):
        fm = qt.QFontMetrics(self.font())
        if (fm.width(txt) > edit.width()) and (edit.width() > 0):
            edit.setToolTip(txt)
        else:
            edit.setToolTip('')

    def registerPropWidget(self, widgets, caption, prop, **kw):
        u"""
        Registers one or more widgets and connects them to one or more
        transformation parameters.

        *widget*: a sequence of widgets or a single widget.

        *caption*: str, will appear in the popup menu in its "apply to" part.

        *prop*: str or a sequence of str, transformation parameter name(s).
        If the wished transformation parameter resides inside a dictionary, a
        chained dot notation can be used, e.g. 'transformParams.aDict.aParam'.

        Optional key words (in *kw*):

        *convertType*: a Python type or a list of types, same length as *prop*,
        that is applied to the widget value.

        *hideEmpty*: bool, applicable to edit GUI elements. If True and the
        *prop* is None or an empty str, the edit element is not visible.

        *emptyMeans*: a value that is assigned to *prop* when the edit element
        is empty.

        *copyValue*: a single value or a list of length of *prop*. When copy
        *prop* to other data items, this specific value can be copied. If
        *copyValue* is a list of length of *prop*, it can mix specific values
        and a str 'from data' that signals that the corresponding prop is taken
        from the actual data transformation parameter.

        *transformNames* list of str
        The transforms to run after the given widgets have changed. Defaults to
        the names in `self.node.transformsIn`.

        *dataItems* list of data items
        None (the transformation parameter will be applied to selected items)
        or 'all' (applied to all items).
        """

        prop = cco.expandTransformParam(prop)
        dataItems = kw.pop('dataItems', None)
        transformNames = kw.pop(
            'transformNames', [tr.name for tr in self.node.transformsIn])
        if isinstance(transformNames, str):
            transformNames = [transformNames]
        if ('correction_' in prop) and (len(transformNames) == 0):
            transformNames = [tr.name for tr in self.node.transformsOut]

        if not isinstance(widgets, (list, tuple)):
            widgets = [widgets]
        for widget in widgets:
            widget.contextMenuEvent = self.contextMenuEvent
            className = widget.metaObject().className().lower()
            for iwt, widgetType in enumerate(propWidgetTypes):
                if widgetType in className:
                    if iwt == 0:  # edit
                        widget.textChanged.connect(
                            partial(self.changeTooltip, widget))
                    elif iwt == 1:  # 'label'
                        pass
                    elif iwt == 2:  # 'spinbox'
                        widget.valueChanged.connect(partial(
                            self.updatePropFromSpinBox, widget, dataItems,
                            prop))
                        widget.setKeyboardTracking(False)
                        widget.editingFinished.connect(partial(
                            self.spinBoxEditingFinished, widget, dataItems,
                            prop))
                        # # uses stepBy():
                        # widget.stepBy = partial(
                        #     stepByWithUpdate, widget, widget.stepBy, self,
                        #     dataItems, prop)
                    elif iwt == 3:  # 'groupbox'
                        # widget.toggled.connect(
                        widget.clicked.connect(
                            partial(self.updatePropFromCheckBox, widget,
                                    dataItems, prop))
                    elif iwt == 4:  # 'checkbox'
                        # widget.toggled.connect(
                        widget.clicked.connect(
                            partial(self.updatePropFromCheckBox, widget,
                                    dataItems, prop))
                    elif iwt == 5:  # 'pushbutton'
                        pass
                    elif iwt == 6:  # 'tableview'
                        pass
                    elif iwt == 7:  # 'combobox'
                        widget.currentIndexChanged.connect(
                            partial(self.updatePropFromComboBox, widget,
                                    dataItems, prop, **kw))
                    elif iwt == 8:  # 'rangewidget' from gui.roi
                        widget.rangeChanged.connect(
                            partial(self.updatePropFromRangeWidget, widget,
                                    dataItems, prop))
                    elif iwt == 9:  # 'statebuttons' from gui.gcommons
                        widget.statesActive.connect(
                            partial(self.updatePropFromStateButtons, widget,
                                    dataItems, prop))
                    elif iwt == 10:  # 'correction' from gui.gcorrection
                        widget.sigCorrectionChanged.connect(
                            partial(self.updatePropFromCorrections, widget,
                                    dataItems, prop))
                    break
            else:
                raise ValueError("unknown widgetType {0}".format(className))

            self.propWidgets[widget] = dict(
                widgetTypeIndex=iwt, caption=caption, prop=prop,
                transformNames=transformNames, kw=kw)
            copyValue = kw.pop('copyValue', None)
            if copyValue is not None:
                if isinstance(prop, (list, tuple)) and \
                        isinstance(copyValue, (list, tuple)):
                    if len(prop) != len(copyValue):
                        raise ValueError(
                            '`prop` and `copyValue` must be of equal lengths')
                self.propWidgets[widget]['copyValue'] = copyValue

    def registerPropGroup(self, groupWidget, widgets, caption):
        u"""Registers a group widget (QGroupBox) that contains individual
        *widgets* , each with its own data properties. This group will appear
        in the copy popup menu.
        """
        self.propGroups[groupWidget] = dict(widgets=widgets, caption=caption)

    def registerExclusivePropGroup(
            self, groupWidget, rbuttons, caption, prop, **kw):
        """A checkable group that contains QRadioButtons that reflect an int
        prop."""
        dataItems = kw.pop('dataItems', None)
        transformNames = kw.pop(
            'transformNames', [tr.name for tr in self.node.transformsIn])
        if isinstance(transformNames, str):
            transformNames = [transformNames]
        prop = cco.expandTransformParam(prop)
        self.exclusivePropGroups[groupWidget] = dict(
            widgets=rbuttons, caption=caption, prop=prop,
            transformNames=transformNames)
        for irb, rb in enumerate(rbuttons):
            rb.clicked.connect(partial(
                self.updatePropFromRadioButton, rb, dataItems, prop, irb))

    def registerExclusivePropGroupWithEdits(
            self, groupWidget, widgets, caption, props, **kw):
        """A group that contains QRadioButton + QLineEdit pairs. Each such pair
        sets an exclusive data property in *props*. The existence of this
        property selects the corresponding QRadioButton."""
        self.exclusivePropGroups[groupWidget] = dict(
            widgets=widgets, caption=caption, props=props, kw=kw)

    def registerStatusLabel(self, widget, prop, **kw):
        u"""
        Registers a status widget (typically QLabel) that gets updated when the
        transformation has been completed. The widget must have `setData()` or
        `setText()` or `setValue()` method.

        Optional key words:

        *hideEmpty*: same as in :meth:`registerPropWidget()`.

        *textFormat*: format specification, as in Python’s `format() function
        <https://docs.python.org/library/string.html#format-specification-mini-language>`_
        e.g. '.4f' .
        """
        prop = cco.expandTransformParam(prop)
        if not any(hasattr(widget, attr)
                   for attr in ['setData', 'setText', 'setValue']):
            className = widget.metaObject().className()
            raise ValueError(
                f"the widget {className} must have "
                "`setData()` or `setText()` or `setValue()` method")
        self.statusWidgets[widget] = dict(prop=prop, kw=kw)

    def keyPressEvent(self, event):
        if event.key() in (qt.Qt.Key_Enter, qt.Qt.Key_Return):
            self.updateDataFromUI()
        elif event.key() in (qt.Qt.Key_Escape, qt.Qt.Key_Backspace):
            if self.node is not None:  # can be True with tests
                self.node.widget.cancelPropsToPickedData()
        event.accept()

    def updateProp(self, key=None, value=None, dataItems=None):
        if dataItems is None:
            dataItems = csi.selectedItems
        elif dataItems == 'all':
            dataItems = csi.allLoadedItems
        if len(dataItems) == 0:
            return

        if key is None or value is None:
            params = {}
            tNames = [dd['transformNames'] for dd in
                      list(self.propWidgets.values()) +
                      list(self.exclusivePropGroups.values())]
            if len(tNames) == 0:
                return
        else:
            for dd in (list(self.propWidgets.values()) +
                       list(self.exclusivePropGroups.values())):
                try:
                    # may start with 'transformParams':
                    if dd['prop'].endswith(key):
                        tNames = dd['transformNames']
                        break
                except Exception:  # dd['prop'] can be a list
                    continue
            else:
                raise ValueError('unknown parameter {0}'.format(key))
            if len(tNames) == 0:
                return
            # if '.' not in key:
            key = cco.expandTransformParam(key)
            gur.pushTransformToUndo(self, dataItems, [key], [value])
            if isinstance(key, (list, tuple)):
                param = key[-1]
            elif isinstance(key, str):
                param = '.'.join(key.split('.')[1:]) if '.' in key else key
            else:
                raise ValueError('unknown key "{0}" of type {1}'.format(
                    key, type(key)))
            params = {param: value}

        # in the case when several transforms come to one node, we need to
        # check which one to run for each data object
        foundTransformNames = dict()
        for data in dataItems:
            foundTrName = None
            for tName in tNames:
                if isinstance(tName, str):
                    foundTrName = tName
                    tr = csi.transforms[tName]
                    if (tr.fromNode.is_between_nodes(
                        data.originNodeName, data.terminalNodeName) and
                        tr.toNode.is_between_nodes(
                            data.originNodeName, data.terminalNodeName)):
                        break
                elif isinstance(tName, (list, tuple)):
                    for tN in tName:
                        foundTrName = tN
                        tr = csi.transforms[tN]
                        if (tr.fromNode.is_between_nodes(
                            data.originNodeName, data.terminalNodeName) and
                            tr.toNode.is_between_nodes(
                                data.originNodeName, data.terminalNodeName)):
                            break
            else:
                trs = csi.nodes[data.originNodeName].transformsOut
                foundTrName = trs[0].name if trs else None
            if foundTrName is None:
                return
            if foundTrName in foundTransformNames:
                foundTransformNames[foundTrName].append(data)
            else:
                foundTransformNames[foundTrName] = [data,]

        if csi.tasker is not None and len(foundTransformNames) == 1:
            trName = list(foundTransformNames.keys())[0]
            tr = csi.transforms[trName]
            csi.tasker.prepare(
                tr, params=params, runDownstream=True, dataItems=dataItems,
                starter=self)
            csi.tasker.thread().start()
        else:
            for trName, trData in foundTransformNames.items():
                tr = csi.transforms[trName]
                tr.run(params=params, dataItems=trData)
                self._onTransformThreadReady(self, trName, props=params)

    # @logger(minLevel=50, attrs=[(0, 'node')])
    def _onTransformThreadReady(
            self, starter, tName='', tStr='', props={}, duration=0, err=None):
        if starter is not self:
            return
        self.updateStatusWidgets()
        self.replotAllDownstream(tName)
        self.extraPlotActionAfterTransform(props)

    def extraPlotActionAfterTransform(self, props):
        return

    def replotAllDownstream(self, tName):
        if hasattr(csi, 'nodesToReplot'):
            for node in csi.nodesToReplot:
                node.widget.replot()

        if tName:
            tr = csi.transforms[tName]
            csi.model.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
            tr.toNode.widget.replot()
            for subnode in tr.toNode.downstreamNodes:
                if subnode.widget is not None:
                    subnode.widget.replot()
        else:
            self.node.widget.replot()
            for subnode in self.node.downstreamNodes:
                if subnode.widget is not None:
                    subnode.widget.replot()

    def updateStatusWidgets(self):
        for widget in self.statusWidgets:
            dd = self.statusWidgets[widget]
            if hasattr(widget, 'setData'):
                widget.setData(dd['prop'], **dd['kw'])
            elif hasattr(widget, 'setText'):
                gpd.setEditFromData(widget, dd['prop'], **dd['kw'])
            elif hasattr(widget, 'setValue'):
                gpd.setSpinBoxFromData(widget, dd['prop'])

    def spinBoxEditingFinished(self, spinBox, dataItems, key):
        # spinBox = self.sender()  # doesn't work in PySide2
        if not spinBox.hasFocus():
            return
        self.updateProp(key, spinBox.value(), dataItems)

    def updatePropFromSpinBox(self, spinBox, dataItems, key, value):
        # spinBox = self.sender()  # doesn't work in PySide2
        if not spinBox.hasFocus():
            return
        self.spinBoxProps = spinBox, dataItems, key, value
        self.spinTimer.start(spinBoxDelay)

    def spinDelayed(self):
        if self.spinBoxProps is None:
            return
        spinBox, dataItems, key, value = self.spinBoxProps
        self.updateProp(key, value, dataItems)
        self.spinBoxProps = None

    def updatePropFromCheckBox(self, checkBox, dataItems, key, value):
        # checkBox = self.sender()  # doesn't work in PySide2
        if not checkBox.hasFocus():
            return
        self.updateProp(key, value, dataItems)

    def updatePropFromRadioButton(self, rButton, dataItems, key, irb, value):
        if not rButton.hasFocus():
            return
        rButton.setChecked(True)
        self.updateProp(key, irb, dataItems)

    def updatePropFromComboBox(self, comboBox, dataItems, key, index,
                               compareWith=None, convertType=None, **kw):
        # comboBox = self.sender()  # doesn't work in PySide2
        if not comboBox.hasFocus():
            return
        if convertType is not None:
            value = convertType()
        else:
            value = compareWith[index] if compareWith is not None else index
        if isinstance(key, (list, tuple)):
            self.updateProp(None, value, dataItems)
        else:
            self.updateProp(key, value, dataItems)

    def updatePropFromRangeWidget(self, widget, dataItems, key, value):
        # if not widget.hasFocus():
        #     return
        self.updateProp(key, value, dataItems)

    def updatePropFromStateButtons(self, widget, dataItems, key, value):
        # if not widget.hasFocus():
        #     return
        self.updateProp(key, value, dataItems)

    def updatePropFromCorrections(self, widget, dataItems, key):
        # # if not widget.hasFocus():
        # #     return
        corrs = widget.getCorrections()

        if dataItems is None:
            dataItems = csi.selectedItems
        if 'correction_' in key:
            param = key.split('.')[-1] if '.' in key else key
            for it in dataItems:
                it.hasChanged = False
                if param in it.transformParams:
                    if len(corrs) != len(it.transformParams[param]):
                        it.hasChanged = True
                    else:
                        try:
                            if corrs != it.transformParams[param]:
                                for corr in corrs + it.transformParams[param]:
                                    if corr['kind'] in ('delete', 'spikes'):
                                        it.hasChanged = True
                                        break
                        except ValueError:  # ambiguous comparison
                            it.hasChanged = True
                it.transformParams[param] = corrs
                if it.hasChanged:
                    it.read_data(runDownstream=True)
                    it.hasChanged = False
            self.updateProp(key, corrs, dataItems)

    def setUIFromData(self):
        for widget in self.exclusivePropGroups:
            dd = self.exclusivePropGroups[widget]
            if 'props' in dd:
                # for Py3 only:
                # gpd.setRButtonGroupWithEditsFromData(
                #     *dd['widgets'], dd['props'])
                # for Py2:
                gpd.setRButtonGroupWithEditsFromData(
                    *(dd['widgets'] + [dd['props']]))
            elif 'prop' in dd:
                gpd.setRButtonGroupFromData(dd['widgets'], dd['prop'])
        for widget in self.propWidgets:
            dd = self.propWidgets[widget]
            prop = dd['prop']
            widgetTypeIndex = dd['widgetTypeIndex']
            if widgetTypeIndex == 0:  # 'edit'
                txt = gpd.setEditFromData(widget, prop, **dd['kw'])
                self.changeTooltip(widget, txt)
            elif widgetTypeIndex == 1:  # 'label'
                pass
            elif widgetTypeIndex == 2:  # 'spinbox'
                gpd.setSpinBoxFromData(widget, prop)
            elif widgetTypeIndex == 3:  # 'groupbox'
                gpd.setCButtonFromData(widget, prop)
            elif widgetTypeIndex == 4:  # 'checkbox'
                gpd.setCButtonFromData(widget, prop)
            elif widgetTypeIndex == 7:  # 'combobox'
                gpd.setComboBoxFromData(widget, prop, **dd['kw'])
            elif widgetTypeIndex == 8:  # 'rangewidget'
                gpd.setRangeWidgetFromData(widget, prop)
            elif widgetTypeIndex == 9:  # 'statebuttons'
                gpd.setStateButtonsFromData(widget, prop)
            elif widgetTypeIndex == 10:  # 'correction'
                gpd.setCorrectionsFromData(widget, prop)
        self.updateStatusWidgets()
        self.extraSetUIFromData()

    def extraSetUIFromData(self):
        pass

    def extraPlot(self):
        pass

    def extraPlotTransform(self, dataItem, xName, x, yName, y):
        return x, y

    def updateDataFromUI(self):
        for widget in self.exclusivePropGroups:
            dd = self.exclusivePropGroups[widget]
            if 'props' in dd:
                gpd.updateDataFromRButtonGroupWithEdits(
                    *(dd['widgets']+[dd['props']]), **dd['kw'])
            elif 'prop' in dd:
                gpd.updateDataFromRButtonGroup(dd['widgets'], dd['prop'])
        for widget in self.propWidgets:
            dd = self.propWidgets[widget]
            if dd['widgetTypeIndex'] == 0:  # 'edit'
                gpd.updateDataFromEdit(widget, dd['prop'], **dd['kw'])
            elif dd['widgetTypeIndex'] == 2:  # 'spinbox'
                gpd.updateDataFromSpinBox(widget, dd['prop'])
            elif dd['widgetTypeIndex'] == 7:  # 'combobox'
                gpd.updateDataFromComboBox(widget, dd['prop'], **dd['kw'])
            elif dd['widgetTypeIndex'] == 8:  # 'rangewidget'
                gpd.updateDataFromRangeWidget(widget, dd['prop'])
        self.updateProp()

    def save_properties(self):
        sec = self.__class__.__name__
        for key in self.properties:
            config.put(config.configTransforms, sec, key,
                       str(self.properties[key]))
        if len(self.plotParams) > 0:
            config.put(config.configTransforms, sec, 'plotParams',
                       str(self.plotParams))
