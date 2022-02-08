# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "23 Jul 2021"
# !!! SEE CODERULES.TXT !!!

from functools import partial
from collections import OrderedDict

from silx.gui import qt

from ..core import singletons as csi
from ..core import commons as cco
from . import undoredo as gur
from . import propsOfData as gpd

propWidgetTypes = ('edit', 'label', 'spinbox', 'groupbox', 'checkbox',
                   'pushbutton', 'tableview', 'combobox')


class QLineEditSelectRB(qt.QLineEdit):
    def __init__(self, parent=None, rb=None):
        super(QLineEditSelectRB, self).__init__(parent)
        self.buddyRB = rb

    def focusInEvent(self, e):
        self.buddyRB.setChecked(True)
        super(QLineEditSelectRB, self).focusInEvent(e)


class PropWidget(qt.QWidget):
    def __init__(self, parent=None, node=None, transform=None):
        super(PropWidget, self).__init__(parent)
        self.node = node
        self.transform = transform
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
        if not self.propWidgets or (len(csi.selectedItems) == 0):
            return
        widgetsOver = self._widgetsAt(event.globalPos())
        out = [w in self.propWidgets or w in self.propGroups or
               w in self.exclusivePropGroups for w in widgetsOver]
        if sum(out) == 0:
            return

        menu = qt.QMenu(self)
        hdf5Path = self.fillMenuApply(widgetsOver, menu)
        if self.transform is not None:
            menu.addSeparator()
            self.fillMenuReset(widgetsOver, menu)

        if hdf5Path:
            menu.addSeparator()
            self._addAction(menu, "go to hdf5 location",
                            partial(self.gotoHDF5, hdf5Path))

        menu.exec_(event.globalPos())

    def fillMenuApply(self, widgetsOver, menu):
        hdf5Path = None
        actionStr = 'apply {0}{1}'
        data = csi.selectedItems[0]

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
                    valueStr = ' = {0}'.format(curValue)
                if widget in self.propWidgets:
                    propWidget = self.propWidgets[widget]
                    if propWidget['widgetTypeIndex'] == 0:  # edit
                        if curValue:
                            if curValue.startswith('silx:'):
                                hdf5Path = curValue
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

        if self.transform is not None:
            keys = self.transform.defaultParams.keys()
            props = [cco.expandTransformParam(key) for key in keys]
            values = [data.transformParams[key] for key in keys]
            actionName = 'apply all params of "{0}" transform to picked data'\
                .format(self.transform.name)
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

        return hdf5Path

    def fillMenuReset(self, widgetsOver, menu):
        actionStr = 'reset {0} to default value{1}'

        for widget in widgetsOver:
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
            elif widget in self.exclusivePropGroups:
                props = self._getPropListExclusiveGroup(widget)
                cap = self.exclusivePropGroups[widget]['caption']
            else:
                continue
            values, validProps = [], []
            for prop in props:
                key = cco.shrinkTransformParam(prop)
                if key in self.transform.defaultParams:
                    values.append(self.transform.defaultParams[key])
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

        keys = self.transform.defaultParams.keys()
        props = [cco.expandTransformParam(key) for key in keys]
        values = list(self.transform.defaultParams.values())
        actionName = 'reset all params of "{0}" transform to default values'\
            .format(self.transform.name)
        self._addAction(
            menu, actionName,
            partial(self.resetProps, props, values, actionName))

        props = [cco.expandTransformParam(key)
                 for transform in csi.transforms.values()
                 for key in transform.defaultParams.keys()]
        values = [transform.defaultParams[key]
                  for transform in csi.transforms.values()
                  for key in transform.defaultParams.keys()]
        actionName = 'reset all params of all transforms to default values'
        self._addAction(
            menu, actionName,
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
        res = self.exclusivePropGroups[widget]['props']
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
        files = self.node.widget.files
        ind = files.model().indexFromH5Path(path, True)
        files.setCurrentIndex(ind)
        files.scrollTo(ind)
        files.dataChanged(ind, ind)

    def changeTooltip(self, edit, txt):
        # fm = qt.QFontMetrics(self.font())
        # if (fm.width(txt) > edit.width()) and (edit.width() > 0):
        if True:
            edit.setToolTip(txt)
        else:
            edit.setToolTip('')

    def registerPropWidget(self, widgets, caption, prop, copyValue=None, **kw):
        """Recognized *kw*:

        *convertType*:
        *hideEmpty*:
        *emptyMeans*:
        *copyValue*:

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
                        widget.valueChanged.connect(
                            partial(self.updatePropFromSpinBox, widget, prop))
                    elif iwt == 3:  # 'groupbox'
                        widget.toggled.connect(
                            partial(self.updatePropFromCheckBox, widget, prop))
                    elif iwt == 4:  # 'checkbox'
                        widget.toggled.connect(
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
            self.propWidgets[widget] = dict(
                widgetTypeIndex=iwt, caption=caption, prop=prop, kw=kw)
            if copyValue is not None:
                if isinstance(prop, (list, tuple)) and \
                        isinstance(copyValue, (list, tuple)):
                    if len(prop) != len(copyValue):
                        raise ValueError(
                            '`prop` and `copyValue` must be of equal lengths')
                self.propWidgets[widget]['copyValue'] = copyValue

    def registerPropGroup(self, groupWidget, widgets, caption):
        """This is a group of individual widgets, each with its own data
        properties."""
        self.propGroups[groupWidget] = dict(widgets=widgets, caption=caption)

    def registerExclusivePropGroup(
            self, groupWidget, widgets, caption, props, **kw):
        """A group that contains QRadioButton + QLineEdit pairs. Each such pair
        sets an exclusive data property in *props*. The existence of this
        property selects the corresponding QRadioButton."""
        self.exclusivePropGroups[groupWidget] = dict(
            widgets=widgets, caption=caption, props=props, kw=kw)

    def registerStatusLabel(self, widget, prop, **kw):
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
        if self.transform is None:
            return
        if key is None or value is None:
            params = {}
        else:
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
            csi.transformer.prepare(
                self.transform, params=params, starter=self)
            csi.transformer.thread().start()
        else:
            self.transform.run(params=params)

    def _onTransformThreadReady(self, starter, duration=0):
        if starter is not self:
            return
        if csi.DEBUG_LEVEL > 50:
            what = '_onTransformThreadReady()'
            where = self.node.name if self.node is not None else ''
            if self.transform is not None:
                where += ' ' + self.transform.name
            print('enter {0} {1}'.format(what, where))
        self.updateStatusWidgets()
        self.replotAllDownstream()
        if csi.DEBUG_LEVEL > 50:
            print('exit {0} {1}'.format(what, where))

    def replotAllDownstream(self):
        if self.transform is not None:
            csi.model.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
            self.transform.toNode.widget.replot()
            for subnode in self.transform.toNode.downstreamNodes:
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

    def updatePropFromSpinBox(self, spinBox, key, value):
        # spinBox = self.sender()  # doesn't work in PySide2
        if not spinBox.hasFocus():
            return
        spinBox.setEnabled(False)  # to prevent double acting
        self.updateProp(key, value)
        spinBox.setEnabled(True)

    def updatePropFromCheckBox(self, checkBox, key, value):
        # checkBox = self.sender()  # doesn't work in PySide2
        if not checkBox.hasFocus():
            return
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
            # for Py3 only:
            # gpd.setRButtonGroupWithEditsFromData(*dd['widgets'], dd['props'])
            # for Py2:
            gpd.setRButtonGroupWithEditsFromData(
                *(dd['widgets'] + [dd['props']]))
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
            gpd.updateDataFromRButtonGroupWithEdits(
                *(dd['widgets']+[dd['props']]), **dd['kw'])
        for widget in self.propWidgets:
            dd = self.propWidgets[widget]
            if dd['widgetTypeIndex'] == 0:  # 'edit'
                gpd.updateDataFromEdit(widget, dd['prop'], **dd['kw'])
            # if dd['widgetTypeIndex'] == 7:  # 'combobox'
            #     gpd.updateDataFromComboBox(widget, dd['prop'])
        self.updateProp()

    def getNextTansform(self):
        """returns the next (in the downstream direction) transform object"""
        nextTrInd = list(csi.transforms.keys()).index(self.transform.name) + 1
        try:
            nextTrName = list(csi.transforms.keys())[nextTrInd]
            return csi.transforms[nextTrName]
        except IndexError:
            return
