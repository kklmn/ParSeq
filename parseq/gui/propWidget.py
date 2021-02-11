# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from functools import partial

from silx.gui import qt
from collections import OrderedDict
from ..core import singletons as csi
from ..core import commons as cco
from . import propsOfData as gpd

widgetTypes = 'edit', 'label'


class QLineEditSelectRB(qt.QLineEdit):
    def __init__(self, parent=None, rb=None):
        super(QLineEditSelectRB, self).__init__(parent)
        self.buddyRB = rb

    def focusInEvent(self, e):
        self.buddyRB.setChecked(True)
        super(QLineEditSelectRB, self).focusInEvent(e)


class PropWidget(qt.QWidget):
    def __init__(self, parent=None, node=None):
        super(PropWidget, self).__init__(parent)
        self.node = node
        self.propWidgets = OrderedDict()
        self.propGroups = OrderedDict()
        self.exclusivePropGroups = OrderedDict()
        # self.setContextMenuPolicy(qt.Qt.CustomContextMenu)
        # self.setContextMenuPolicy(qt.Qt.DefaultContextMenu)
        # self.customContextMenuRequested.connect(self.onCustomContextMenu)

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
        # print(out, sum(out))
        if sum(out) == 0:
            return

        menu = qt.QMenu(self)
        hdf5Path = None
        for widgetOver in widgetsOver:
            value = None
            if widgetOver in self.propWidgets:
                propWidget = self.propWidgets[widgetOver]
                value = cco.getDotAttr(
                    csi.selectedItems[0], propWidget['prop'])
                cap = '{0} {1}'.format(propWidget['caption'], value)
            elif widgetOver in self.propGroups:
                propGroup = self.propGroups[widgetOver]
                cap = propGroup['caption']
                # menu.addSeparator()
            elif widgetOver in self.exclusivePropGroups:
                exclusivePropGroup = self.exclusivePropGroups[widgetOver]
                cap = exclusivePropGroup['caption']
                # menu.addSeparator()
            else:
                continue
            self._addAction(menu, "set {0} for picked data".format(cap),
                            partial(self.startPick, widgetOver))  # "Ctrl+P")
            if value and propWidget['widgetTypeIndex'] == 0:  # 'edit'
                if value.startswith('silx:'):
                    hdf5Path = value
        if hdf5Path:
            menu.addSeparator()
            self._addAction(menu, "go to hdf5 location",
                            partial(self.gotoHDF5, hdf5Path))

        menu.exec(event.globalPos())

    def _getProps(self, widget):
        if widget in self.propWidgets:
            return [self.propWidgets[widget]['prop']]
        elif widget in self.exclusivePropGroups:
            return [self.exclusivePropGroups[widget]['props']]
        elif widget in self.propGroups:
            res = []
            for w in self.propGroups[widget]['widgets']:
                res.extend(self._getProps(w))
            return res
        else:
            raise ValueError('wrong property widget')

    def startPick(self, widget):
        self.pendingPropSource = csi.selectedItems[0]
        self.pendingProps = self._getProps(widget)
        self.node.widget.preparePickData(self)

    def gotoHDF5(self, path):
        files = self.node.widget.files
        ind = files.model().indexFromH5Path(path, True)
        files.setCurrentIndex(ind)
        files.scrollTo(ind)
        files.dataChanged(ind, ind)

    def applyPendingProps(self):
        gpd.copyProps(self.pendingPropSource, self.pendingProps)
        self.updateChangedData()

    def changeTooltip(self, txt, edit=None):
        # fm = qt.QFontMetrics(self.font())
        if edit is None:
            edit = self.sender()
        # if (fm.width(txt) > edit.width()) and (edit.width() > 0):
        if True:
            edit.setToolTip(txt)
        else:
            edit.setToolTip('')

    def registerPropWidget(self, widgets, caption, prop, **kw):
        if not isinstance(widgets, (list, tuple)):
            widgets = [widgets]
        for widget in widgets:
            widget.contextMenuEvent = self.contextMenuEvent
            className = widget.metaObject().className().lower()
            for iwt, widgetType in enumerate(widgetTypes):
                if widgetType in className:
                    if iwt == 0:  # edit
                        widget.textChanged.connect(self.changeTooltip)
                    break
            else:
                raise ValueError("unknown widgetType {0}".format(className))
            self.propWidgets[widget] = dict(
                widgetTypeIndex=iwt, caption=caption, prop=prop, kw=kw)

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

    def keyPressEvent(self, event):
        if event.key() in (qt.Qt.Key_Enter, qt.Qt.Key_Return):
            self.updateDataFromUI()
        elif event.key() in (qt.Qt.Key_Escape, qt.Qt.Key_Backspace):
            self.node.widget.cancelPropsToPickedData()
        event.accept()

    def updateProp(self, key, value):
        if self.params[key] == value:
            return
        self.transform.run({key: value})
        self.transform.toNode.widget.replot()
        for subnode in self.transform.toNode.downstreamNodes:
            subnode.widget.replot()

    def updatePropFromSpinBox(self, key, value):
        self.updateProp(key, value)

    def updatePropFromCheckBox(self, key, value):
        self.updateProp(key, value)

    def updatePropFromComboBox(self, key, index, indexToValue=None):
        value = indexToValue[index] if indexToValue is not None else index
        self.updateProp(key, value)

    def setUIFromData(self):
        for widget in self.exclusivePropGroups:
            dd = self.exclusivePropGroups[widget]
            gpd.setRButtonGroupWithEditsFromData(*dd['widgets'], dd['props'])
        for widget in self.propWidgets:
            dd = self.propWidgets[widget]
            if dd['widgetTypeIndex'] == 0:  # 'edit'
                txt = gpd.setEditFromData(widget, dd['prop'], **dd['kw'])
                self.changeTooltip(txt, widget)

    def updateDataFromUI(self):
        for widget in self.exclusivePropGroups:
            dd = self.exclusivePropGroups[widget]
            gpd.updateDataFromRButtonGroupWithEdits(
                *dd['widgets'], dd['props'], **dd['kw'])
        for widget in self.propWidgets:
            dd = self.propWidgets[widget]
            if dd['widgetTypeIndex'] == 0:  # 'edit'
                gpd.updateDataFromEdit(widget, dd['prop'], **dd['kw'])
        self.updateChangedData()

    def updateChangedData(self):
        raise NotImplementedError("'updateChangedData' must be implemented")
