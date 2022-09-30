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
__date__ = "23 Jul 2021"
# !!! SEE CODERULES.TXT !!!

from functools import partial
from collections import OrderedDict
import reprlib

from silx.gui import qt

from ..core import singletons as csi
from ..core import commons as cco
from . import undoredo as gur
from . import propsOfData as gpd

propWidgetTypes = ('edit', 'label', 'spinbox', 'groupbox', 'checkbox',
                   'pushbutton', 'tableview', 'combobox')


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


#  to replace the standard stepBy method of a SpinBox without inheritance:
def stepByWithUpdate(self, oldStepBy, parent, key, steps):
    oldStepBy(steps)
    self.setEnabled(False)  # to prevent double acting
    parent.updateProp(key, self.value())
    self.setEnabled(True)


class PropWidget(qt.QWidget):
    u"""The base class for user transformation widgets and a few internal
    ParSeq widgets. The main idea of this class is to automatize a number of
    tasks: setting GUI from data, changing transformation parameters of data
    from GUI, copying parameters to other data, starting transformation and
    inserting user changes into undo and redo lists.
    """

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

        if csi.transformer is not None:
            csi.transformer.ready.connect(self._onTransformThreadReady)

    def _addAction(self, menu, text, slot, shortcut=None):
        action = qt.QAction(text, self)
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
        tNames = [self.propWidgets[w]['transformName'] for w in widgetsOver
                  if w in self.propWidgets]
        tName = tNames[0] if len(tNames) > 0 else None

        menu = qt.QMenu(self)
        self.fillMenuApply(widgetsOver, menu)
        if tName is not None:
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

        menu.exec_(event.globalPos())

    def fillMenuApply(self, widgetsOver, menu):
        if len(csi.selectedItems) == 0:
            return
        actionStr = 'apply {0}{1}'
        data = csi.selectedItems[0]

        tName = None
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
                tName = propWidget['transformName']
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
            if csi.DEBUG_LEVEL > 10:
                print('widget in widgetsOver')
                print('actionName', actionName)
                print('props', props)
                print('values', values)

        if tName is not None:
            tr = csi.transforms[tName]
            keys = tr.defaultParams.keys()
            props = [cco.expandTransformParam(key) for key in keys]
            values = [data.transformParams[key] for key in keys]
            actionName = 'apply all params of "{0}" transform to picked data'\
                .format(tName)
            actionName2 = actionName + ' to picked data'
            self._addAction(
                menu, actionName2,
                partial(self.startPick, props, values, actionName))
            if csi.DEBUG_LEVEL > 10:
                print('apply all params of the transform')
                print('actionName', actionName)
                print('props', props)
                print('values', values)

            props = [cco.expandTransformParam(key)
                     for key in data.transformParams.keys()]
            values = list(data.transformParams.values())
            actionName = 'apply all params of all transforms to picked data'
            actionName2 = actionName + ' to picked data'
            self._addAction(
                menu, actionName2,
                partial(self.startPick, props, values, actionName))
            if csi.DEBUG_LEVEL > 10:
                print('apply all params of all transforms')
                print('actionName', actionName)
                print('props', props)
                print('values', values)

    def fillMenuReset(self, widgetsOver, menu):
        actionStr = 'reset {0} to default value{1}'

        tr = None
        for widget in widgetsOver:
            tName = None
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
                tName = self.propWidgets[widget]['transformName']
            elif widget in self.exclusivePropGroups:
                props = self._getPropListExclusiveGroup(widget)
                cap = self.exclusivePropGroups[widget]['caption']
            else:
                continue
            values, validProps = [], []
            if tName is not None:
                tr = csi.transforms[tName]
                for prop in props:
                    key = cco.shrinkTransformParam(prop)
                    if key in tr.defaultParams:
                        values.append(tr.defaultParams[key])
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
        actionName = 'reset all params of "{0}" transform to default values'\
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
        if csi.DEBUG_LEVEL > 10:
            print('startPick')
            print('pendingActionName', self.pendingActionName)
            print('pendingProps', self.pendingProps)
            print('pendingValues', self.pendingValues)
        if self.node is not None:  # can be True with tests
            self.node.widget.preparePickData(self)

    def applyPendingProps(self):
        if csi.DEBUG_LEVEL > 10:
            print('applyPendingProps')
            print('pendingActionName', self.pendingActionName)
            print('pendingProps', self.pendingProps)
            print('pendingValues', self.pendingValues)
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
        _, items, params, prevValues, values, _ = lastAction
        nChanged = 0
        for item, prevs in zip(items, prevValues):
            nChanged += gpd.copyProps([item], params, prevs,
                                      self.shouldRemoveNonesFromProps)
        if not nChanged:
            csi.mainWindow.displayStatusMessage('no changes')
            return
        self.updateProp()
        self.setUIFromData()

    def redoProps(self, lastAction):
        _, items, params, prevValues, values, _ = lastAction
        nChanged = gpd.copyProps(items, params, values,
                                 self.shouldRemoveNonesFromProps)
        if not nChanged:
            csi.mainWindow.displayStatusMessage('no changes')
            return
        self.updateProp()
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
        """
        Registers one or more widgets and connects them to one or more
        transformation parameters.

        *widget*: a sequence of widgets or a single widget.

        *caption*: str, will appear in the popup menu in its "apply to" part.

        *prop*: str or a sequence of str, transformation parameter name(s).

        Optional key words:

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

        *transformName* str, the transform to run after the given widgets have
        changed. Defaults to `self.node.transformIn.name`.
        """

        prop = cco.expandTransformParam(prop)
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
                        # this method is bad as does updateProp while typing
                        # widget.valueChanged.connect(partial(
                        #     self.updatePropFromSpinBox, widget, prop))
                        # replaced with using stepBy():
                        widget.stepBy = partial(
                            stepByWithUpdate, widget, widget.stepBy, self,
                            prop)
                    elif iwt == 3:  # 'groupbox'
                        # widget.toggled.connect(
                        widget.clicked.connect(
                            partial(self.updatePropFromCheckBox, widget, prop))
                    elif iwt == 4:  # 'checkbox'
                        # widget.toggled.connect(
                        widget.clicked.connect(
                            partial(self.updatePropFromCheckBox, widget, prop))
                    elif iwt == 5:  # 'pushbutton'
                        pass
                    elif iwt == 6:  # 'tableview'
                        pass
                    elif iwt == 7:  # 'combobox'
                        pass
                    break
            else:
                raise ValueError("unknown widgetType {0}".format(className))

            try:
                # transformName = self.node.transformsOut[0].name
                transformName = kw.pop(
                    'transformName', self.node.transformIn.name)
            except Exception:
                transformName = None
            self.propWidgets[widget] = dict(
                widgetTypeIndex=iwt, caption=caption, prop=prop,
                transformName=transformName, kw=kw)
            copyValue = kw.pop('copyValue', None)
            if copyValue is not None:
                if isinstance(prop, (list, tuple)) and \
                        isinstance(copyValue, (list, tuple)):
                    if len(prop) != len(copyValue):
                        raise ValueError(
                            '`prop` and `copyValue` must be of equal lengths')
                self.propWidgets[widget]['copyValue'] = copyValue

    def registerPropGroup(self, groupWidget, widgets, caption):
        u"""
        Registers a group widget (QGroupBox) that contains individual
        *widgets*, each with its own data properties. This group will appear in
        the copy popup menu.
        """

        self.propGroups[groupWidget] = dict(widgets=widgets, caption=caption)

    def registerExclusivePropGroup(
            self, groupWidget, rbuttons, caption, prop, transformName):
        """A checkable group that contains QRadioButtons that reflect an int
        prop."""
        prop = cco.expandTransformParam(prop)
        self.exclusivePropGroups[groupWidget] = dict(
            widgets=rbuttons, caption=caption, prop=prop,
            transformName=transformName)
        for irb, rb in enumerate(rbuttons):
            rb.clicked.connect(partial(
                self.updatePropFromRadioButton, groupWidget, prop, irb))

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
        `setText()` method.

        Optional key words:

        *hideEmpty*: same as in :meth:`registerPropWidget()`.

        *textFormat*: format specification, as in Python’s `format() function
        <https://docs.python.org/library/string.html#format-specification-mini-language>`_
        e.g. '.4f' .
        """
        prop = cco.expandTransformParam(prop)
        if not (hasattr(widget, 'setData') or hasattr(widget, 'setText')):
            className = widget.metaObject().className()
            raise ValueError(
                "the widget {} must have `setData()` or `setText()` method"
                .format(className))
        self.statusWidgets[widget] = dict(prop=prop, kw=kw)

    def keyPressEvent(self, event):
        if event.key() in (qt.Qt.Key_Enter, qt.Qt.Key_Return):
            self.updateDataFromUI()
        elif event.key() in (qt.Qt.Key_Escape, qt.Qt.Key_Backspace):
            if self.node is not None:  # can be True with tests
                self.node.widget.cancelPropsToPickedData()
        event.accept()

    def updateProp(self, key=None, value=None):
        if key is None or value is None:
            params = {}
            tNames = [dd['transformName'] for dd in
                      list(self.propWidgets.values()) +
                      list(self.exclusivePropGroups.values())]
            tName = tNames[0] if len(tNames) > 0 else None
            if tName:
                tr = csi.transforms[tName]
            else:
                return
        else:
            for dd in (list(self.propWidgets.values()) +
                       list(self.exclusivePropGroups.values())):
                try:
                    if dd['prop'].endswith(key):
                        # may start with 'transformParams'
                        tName = dd['transformName']
                        break
                except Exception:  # dd['prop'] can be a list
                    continue
            else:
                raise ValueError('unknown parameter {0}'.format(key))
            if tName:
                tr = csi.transforms[tName]
            else:
                return
            if '.' not in key:
                key = cco.expandTransformParam(key)
            dataItems = csi.selectedItems
            gur.pushTransformToUndo(self, dataItems, [key], [value])
            if isinstance(key, (list, tuple)):
                param = key[-1]
            elif isinstance(key, type('')):
                param = key.split('.')[-1] if '.' in key else key
            else:
                raise ValueError('unknown key "{0}" of type {1}'.format(
                    key, type(key)))
            params = {param: value}

        if csi.transformer is not None:
            csi.transformer.prepare(tr, params=params, starter=self)
            csi.transformer.thread().start()
        else:
            tr.run(params=params)

    def _onTransformThreadReady(self, starter, tName='', duration=0, err=None):
        if starter is not self:
            return
        if csi.DEBUG_LEVEL > 50:
            what = '_onTransformThreadReady()'
            where = self.node.name if self.node is not None else ''
            if tName:
                where += ' ' + tName
            print('enter {0} {1}'.format(what, where))
        self.updateStatusWidgets()
        self.replotAllDownstream(tName)
        if csi.DEBUG_LEVEL > 50:
            print('exit {0} {1}'.format(what, where))

    def replotAllDownstream(self, tName):
        if tName:
            tr = csi.transforms[tName]
            csi.model.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
            tr.toNode.widget.replot()
            for subnode in tr.toNode.downstreamNodes:
                subnode.widget.replot()
        else:
            self.node.widget.replot()
            for subnode in self.node.downstreamNodes:
                subnode.widget.replot()

    def updateStatusWidgets(self):
        for widget in self.statusWidgets:
            dd = self.statusWidgets[widget]
            if hasattr(widget, 'setData'):
                widget.setData(dd['prop'], **dd['kw'])
            elif hasattr(widget, 'setText'):
                gpd.setEditFromData(widget, dd['prop'], **dd['kw'])

    # def updatePropFromSpinBox(self, spinBox, key, value):
    #     # spinBox = self.sender()  # doesn't work in PySide2
    #     if not spinBox.hasFocus():
    #         return
    #     spinBox.setEnabled(False)  # to prevent double acting
    #     self.updateProp(key, value)
    #     spinBox.setEnabled(True)

    def updatePropFromCheckBox(self, checkBox, key, value):
        # checkBox = self.sender()  # doesn't work in PySide2
        if not checkBox.hasFocus():
            return
        self.updateProp(key, value)

    def updatePropFromRadioButton(self, rButton, key, value, **kw):
        self.updateProp(key, value)

    def updatePropFromComboBox(self, comboBox, key, index, indexToValue=None):
        # comboBox = self.sender()  # doesn't work in PySide2
        if not comboBox.hasFocus():
            return
        value = indexToValue[index] if indexToValue is not None else index
        self.updateProp(key, value)

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
            if dd['widgetTypeIndex'] == 0:  # 'edit'
                txt = gpd.setEditFromData(widget, dd['prop'], **dd['kw'])
                self.changeTooltip(widget, txt)
            elif dd['widgetTypeIndex'] == 1:  # 'label'
                pass
            elif dd['widgetTypeIndex'] == 2:  # 'spinbox'
                gpd.setSpinBoxFromData(widget, dd['prop'])
            elif dd['widgetTypeIndex'] == 3:  # 'groupbox'
                gpd.setCButtonFromData(widget, dd['prop'])
            elif dd['widgetTypeIndex'] == 4:  # 'checkbox'
                gpd.setCButtonFromData(widget, dd['prop'])
            elif dd['widgetTypeIndex'] == 7:  # 'combobox'
                gpd.setComboBoxFromData(widget, dd['prop'])
        self.updateStatusWidgets()
        self.extraSetUIFromData()

    def extraSetUIFromData(self):
        pass

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
            # elif dd['widgetTypeIndex'] == 7:  # 'combobox'
            #     gpd.updateDataFromComboBox(widget, dd['prop'])
        self.updateProp()
