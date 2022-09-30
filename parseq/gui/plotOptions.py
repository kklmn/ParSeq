# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "15 Jul 2022"
# !!! SEE CODERULES.TXT !!!

from collections import OrderedDict
from functools import partial
from silx.gui import qt

from ..core import singletons as csi
from ..core import commons as cco
from ..gui import gcommons as gco
from . import propsOfData as gpd

lineStyles = {
    None: qt.Qt.NoPen,
    'None': qt.Qt.NoPen,
    'none': qt.Qt.NoPen,
    '': qt.Qt.NoPen,
    ' ': qt.Qt.NoPen,
    '-': qt.Qt.SolidLine,
    '--': qt.Qt.DashLine,
    '.': qt.Qt.DotLine,
    ':': qt.Qt.DotLine,
    '-.': qt.Qt.DashDotLine
}

lineStylesText = OrderedDict([
    ('no line', ' '), ('solid', '-'), ('dashed', '--'), ('dash-dot', '-.'),
    ('dotted', ':'), ('', '')])

# Build all lineSymbols, from pyqtgraph
lineSymbols = dict([(name, qt.QPainterPath())
                    for name in ['o', 's', 't', 'd', '+', 'x', '.', ',']])
lineSymbols['o'].addEllipse(qt.QRectF(.1, .1, .8, .8))
lineSymbols['.'].addEllipse(qt.QRectF(.3, .3, .4, .4))
lineSymbols[','].addEllipse(qt.QRectF(.4, .4, .2, .2))
lineSymbols['s'].addRect(qt.QRectF(.1, .1, .8, .8))

coords = {
    't': [(0.5, 0.), (.1, .8), (.9, .8)],
    'd': [(0.1, 0.5), (0.5, 0.), (0.9, 0.5), (0.5, 1.)],
    '+': [(0.0, 0.40), (0.40, 0.40), (0.40, 0.), (0.60, 0.),
          (0.60, 0.40), (1., 0.40), (1., 0.60), (0.60, 0.60),
          (0.60, 1.), (0.40, 1.), (0.40, 0.60), (0., 0.60)],
    'x': [(0.0, 0.40), (0.40, 0.40), (0.40, 0.), (0.60, 0.),
          (0.60, 0.40), (1., 0.40), (1., 0.60), (0.60, 0.60),
          (0.60, 1.), (0.40, 1.), (0.40, 0.60), (0., 0.60)]
}
for s, c in coords.items():
    lineSymbols[s].moveTo(*c[0])
    for x, y in c[1:]:
        lineSymbols[s].lineTo(x, y)
    lineSymbols[s].closeSubpath()
tr = qt.QTransform()
tr.rotate(45)
lineSymbols['x'].translate(qt.QPointF(-0.5, -0.5))
lineSymbols['x'] = tr.map(lineSymbols['x'])
lineSymbols['x'].translate(qt.QPointF(0.5, 0.5))

noSymbols = ('None', 'none', '', ' ')

lineSymbolsText = OrderedDict([
    ('no symbol', 'None'), ('circle', 'o'), ('point', '.'), ('pixel', ','),
    ('cross', '+'), ('x-cross', 'x'), ('diamond', 'd'), ('square', 's'),
    ('', '')])


class LineStyleDelegate(qt.QItemDelegate):
    def paint(self, painter, option, index):
        txt = index.data(qt.Qt.DisplayRole)
        if txt.startswith('no'):
            super().paint(painter, option, index)
            return
        lineStyle = lineStyles[lineStylesText[txt]]
        painter.save()
        painter.setRenderHint(qt.QPainter.Antialiasing, False)
        rect = option.rect
        rect.adjust(+5, 0, -5, 0)
        pen = qt.QPen()
        pen.setColor(qt.QColor(self.parent().color))
        pen.setWidthF(self.parent().widthSpinBox.value() + 0.5)
        pen.setStyle(lineStyle)
        painter.setPen(pen)
        middle = round((rect.bottom() + rect.top()) / 2)
        painter.drawLine(rect.left(), middle, rect.right(), middle)
        painter.restore()


class LineStyleComboBox(qt.QComboBox):
    def paintEvent(self, e):
        txt = self.currentText()
        if txt.startswith('no'):
            super().paintEvent(e)
            return
        lineStyle = lineStyles[lineStylesText[txt]]
        p = qt.QStylePainter(self)
        p.setPen(self.palette().color(qt.QPalette.Text))
        opt = qt.QStyleOptionComboBox()
        self.initStyleOption(opt)
        p.drawComplexControl(qt.QStyle.CC_ComboBox, opt)
        painter = qt.QPainter(self)
        painter.save()
        painter.setRenderHint(qt.QPainter.Antialiasing, False)
        rect = p.style().subElementRect(
            qt.QStyle.SE_ComboBoxFocusRect, opt, self)
        rect.adjust(+5, 0, -5, 0)
        pen = qt.QPen()
        pen.setColor(qt.QColor(self.parent().color))
        pen.setWidthF(self.parent().widthSpinBox.value() + 0.5)
        pen.setStyle(lineStyle)
        painter.setPen(pen)
        middle = round((rect.bottom() + rect.top()) / 2)
        painter.drawLine(rect.left(), middle, rect.right(), middle)
        painter.restore()


class SymbolDelegate(qt.QItemDelegate):
    def paint(self, painter, option, index):
        txt = index.data(qt.Qt.DisplayRole)
        if txt == '':
            return
        if txt.startswith('no'):
            super().paint(painter, option, index)
            return
        lineSymbol = lineSymbols[lineSymbolsText[txt]]
        painter.save()
        painter.setRenderHint(qt.QPainter.Antialiasing, True)
        rect = option.rect
        rect.adjust(+5, 0, -5, 0)

        symbolFC = qt.QColor(self.parent().color)
        symbolEC = qt.QColor(self.parent().color)
        # symbolSize = self.parent().sizeSpinBox.value() * 2
        symbolSize = (self.parent().sizeSpinBox.value() + 1) * 1.75
        symbolPath = qt.QPainterPath(lineSymbol)
        scale = symbolSize
        painter.scale(scale, scale)
        symbolOffset = qt.QPointF(
            (rect.left() + rect.right() - symbolSize)*0.5 / scale,
            (rect.top() + rect.bottom() - symbolSize)*0.5 / scale)
        symbolPath.translate(symbolOffset)
        symbolBrush = qt.QBrush(symbolFC, qt.Qt.SolidPattern)
        symbolPen = qt.QPen(symbolEC, 1./scale, qt.Qt.SolidLine)
        painter.setPen(symbolPen)
        painter.setBrush(symbolBrush)
        painter.drawPath(symbolPath)
        painter.restore()


class SymbolComboBox(qt.QComboBox):
    def paintEvent(self, e):
        txt = self.currentText()
        if txt == '':
            return
        if txt.startswith('no'):
            super().paintEvent(e)
            return
        lineSymbol = lineSymbols[lineSymbolsText[txt]]
        p = qt.QStylePainter(self)
        p.setPen(self.palette().color(qt.QPalette.Text))
        opt = qt.QStyleOptionComboBox()
        self.initStyleOption(opt)
        p.drawComplexControl(qt.QStyle.CC_ComboBox, opt)
        painter = qt.QPainter(self)
        painter.save()
        painter.setRenderHint(qt.QPainter.Antialiasing, True)
        rect = p.style().subElementRect(
            qt.QStyle.SE_ComboBoxFocusRect, opt, self)
        rect.adjust(+5, 0, -5, 0)

        symbolFC = qt.QColor(self.parent().color)
        symbolEC = qt.QColor(self.parent().color)
        symbolSize = self.parent().sizeSpinBox.value() * 2
        symbolPath = qt.QPainterPath(lineSymbol)
        scale = symbolSize
        painter.scale(scale, scale)
        symbolOffset = qt.QPointF(
            (rect.left() + rect.right() - symbolSize)*0.5 / scale,
            (rect.top() + rect.bottom() - symbolSize)*0.5 / scale)
        symbolPath.translate(symbolOffset)
        symbolBrush = qt.QBrush(symbolFC, qt.Qt.SolidPattern)
        symbolPen = qt.QPen(symbolEC, 1./scale, qt.Qt.SolidLine)
        painter.setPen(symbolPen)
        painter.setBrush(symbolBrush)
        painter.drawPath(symbolPath)
        painter.restore()


class QColorLoop(qt.QPushButton):
    LINE_WIDTH = 4

    def __init__(self, parent, colorCycle=[]):
        self.colorCycle = colorCycle
        super().__init__(parent)
        self.setFixedHeight(self.LINE_WIDTH*len(colorCycle)+2*self.LINE_WIDTH)
        self.setMinimumWidth(20)

    def paintEvent(self, e):
        super().paintEvent(e)
        rect = e.rect()
        painter = qt.QPainter(self)
        painter.setRenderHint(qt.QPainter.Antialiasing, False)
        painter.save()
        pen = qt.QPen()
        pen.setWidthF(self.LINE_WIDTH)
        pen.setStyle(qt.Qt.SolidLine)
        for ic, color in enumerate(self.colorCycle):
            pen.setColor(qt.QColor(color))
            painter.setPen(pen)
            pos = round((ic+1.5) * self.LINE_WIDTH)
            painter.drawLine(rect.left() + 2*self.LINE_WIDTH, pos,
                             rect.right() - 2*self.LINE_WIDTH, pos)
        painter.restore()


class LineProps(qt.QDialog):
    def __init__(self, parent, node, activeTab=None):
        super().__init__(parent)
        self.setWindowTitle("Line properties")

        self.isGroupSelected = False
        self.isTopGroupSelected = False
        for topItem in csi.selectedTopItems:
            if topItem.child_count() == 0:
                break
        else:
            self.isGroupSelected = True  # all selected items are groups

        lsi = len(csi.selectedTopItems)
        if self.isGroupSelected:
            if lsi == 1:
                group = csi.selectedTopItems[0]
                txt = '... of group <b>{0}</b> with {1} item{2}'.format(
                    group.alias, group.child_count(),
                    's' if group.child_count() > 1 else '')
            elif lsi > 1:
                txt = "... of {0} selected groups".format(lsi)
            else:
                txt = ''
        else:
            if csi.selectedTopItems == csi.dataRootItem.get_nongroups():
                self.isTopGroupSelected = True
                txt = "... of all top level data"
            elif len(csi.allLoadedItems) == len(csi.selectedItems):
                txt = "... of all data"
            else:
                if lsi == 1:
                    txt = "... of 1 selected item ({0})".format(
                        csi.selectedItems[0].alias)
                else:
                    txt = "... of {0} selected items".format(lsi)
        nSpectraLabel = qt.QLabel(txt)

        self.color = self.color1 = self.color2 = 'k'
        self.colorSeq = 0  # controls which color to edit 1 or 2 for Gradient
        self.colorPolicy = gco.COLOR_POLICY_LOOP1
        groupColor = self.makeColorGroup()

        self.tabWidget = qt.QTabWidget(parent=self)
        self.tabs = []
        self.node = node
        yNs = node.get_arrays_prop('qLabel', role='y')
        for yN in yNs:
            tab = self.makeTab()
            self.tabWidget.addTab(tab, yN)
            self.tabs.append(tab)
        if activeTab is not None:
            self.tabWidget.setCurrentIndex(activeTab)

        mainLayout = qt.QVBoxLayout()
        mainLayout.addWidget(nSpectraLabel)
        mainLayout.addWidget(groupColor)
        mainLayout.addWidget(self.tabWidget)
        buttonBox = qt.QDialogButtonBox(
            qt.QDialogButtonBox.Ok | qt.QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)  # OK button
        buttonBox.rejected.connect(self.reject)  # Cancel button
        mainLayout.addStretch()
        mainLayout.addWidget(buttonBox)
        self.setLayout(mainLayout)
        self.setSizePolicy(qt.QSizePolicy.Minimum, qt.QSizePolicy.Minimum)

        self.setUIFromData()

    def makeColorGroup(self):
        self.colorIndividual = qt.QRadioButton("individual")
        self.colorIndividualButton = QColorLoop(self, [self.color])
        self.colorIndividualButton.clicked.connect(
            partial(self.openColorDialog, gco.COLOR_POLICY_INDIVIDUAL))
        self.colorLoop1 = qt.QRadioButton("loop1")
        self.colorLoop1Button = QColorLoop(self, gco.colorCycle1)
        self.colorLoop1Button.clicked.connect(
            partial(self.openColorDialog, gco.COLOR_POLICY_LOOP1))
        self.colorLoop2 = qt.QRadioButton("loop2")
        self.colorLoop2Button = QColorLoop(self, gco.colorCycle2)
        self.colorLoop2Button.clicked.connect(
            partial(self.openColorDialog, gco.COLOR_POLICY_LOOP2))
        self.colorGradient = qt.QRadioButton("gradient")
        gradient = gco.makeGradientCollection(self.color1, self.color2)
        self.colorGradientButton = QColorLoop(self, gradient)
        self.colorGradientButton.clicked.connect(
            partial(self.openColorDialog, gco.COLOR_POLICY_GRADIENT))
        self.colorAutoCollective = qt.QCheckBox(
            "keep collective color rule\nwhen data model changes")
        self.colorAutoCollective.setEnabled(
            self.isGroupSelected or self.isTopGroupSelected)
        self.colorRadioButtons = (self.colorIndividual, self.colorLoop1,
                                  self.colorLoop2, self.colorGradient)

        layoutC = qt.QVBoxLayout()
        layoutC.setContentsMargins(10, 0, 2, 2)
        layoutH = qt.QHBoxLayout()
        layoutH.addWidget(self.colorIndividual)
        layoutH.addWidget(self.colorIndividualButton)
        layoutC.addLayout(layoutH)
        layoutH = qt.QHBoxLayout()
        layoutH.addWidget(self.colorLoop1)
        layoutH.addWidget(self.colorLoop1Button)
        layoutC.addLayout(layoutH)
        layoutH = qt.QHBoxLayout()
        layoutH.addWidget(self.colorLoop2)
        layoutH.addWidget(self.colorLoop2Button)
        layoutC.addLayout(layoutH)
        layoutH = qt.QHBoxLayout()
        layoutH.addWidget(self.colorGradient)
        layoutH.addWidget(self.colorGradientButton)
        layoutC.addLayout(layoutH)
        layoutC.addWidget(self.colorAutoCollective)

        groupColor = qt.QGroupBox('Color:')
        groupColor.setLayout(layoutC)
        return groupColor

    def makeTab(self):
        tab = qt.QWidget(self)
        tab.color = self.color

        layout2 = qt.QHBoxLayout()
        layout2.addWidget(qt.QLabel('Symbol:'))
        tab.symbolComboBox = SymbolComboBox(tab)
        symbolDelegate = SymbolDelegate(tab)
        tab.symbolComboBox.setItemDelegate(symbolDelegate)
        tab.symbolComboBox.addItems(tuple(lineSymbolsText.keys()))
        tab.symbolComboBox.currentIndexChanged.connect(
            partial(self.comboBoxChanged, tab, "size"))
        layout2.addWidget(tab.symbolComboBox, 1)
        tab.sizeLabel = qt.QLabel('Size:')
        layout2.addWidget(tab.sizeLabel)
        tab.sizeSpinBox = qt.QDoubleSpinBox()
        tab.sizeSpinBox.setDecimals(0)
        tab.sizeSpinBox.setMaximum(10)
        tab.sizeSpinBox.setMinimum(1)
        tab.sizeSpinBox.setSingleStep(1)
        tab.sizeSpinBox.valueChanged.connect(
            partial(self.updateFromSpinBox, tab, "size"))
        layout2.addWidget(tab.sizeSpinBox, 0)

        layout3 = qt.QHBoxLayout()
        layout3.addWidget(qt.QLabel('Style:'))
        tab.styleComboBox = LineStyleComboBox(tab)
        lineStyleDelegate = LineStyleDelegate(tab)
        tab.styleComboBox.setItemDelegate(lineStyleDelegate)
        tab.styleComboBox.addItems(tuple(lineStylesText.keys()))
        tab.styleComboBox.currentIndexChanged.connect(
            partial(self.comboBoxChanged, tab, "width"))
        layout3.addWidget(tab.styleComboBox, 1)
        tab.widthLabel = qt.QLabel('Width:')
        layout3.addWidget(tab.widthLabel)
        tab.widthSpinBox = qt.QDoubleSpinBox()
        tab.widthSpinBox.setDecimals(1)
        tab.widthSpinBox.setMaximum(10)
        tab.widthSpinBox.setMinimum(0.1)
        tab.widthSpinBox.setSingleStep(0.5)
        tab.widthSpinBox.valueChanged.connect(
            partial(self.updateFromSpinBox, tab, "width"))
        layout3.addWidget(tab.widthSpinBox, 0)

        layout4 = qt.QHBoxLayout()
        tab.yAxisLabel = qt.QLabel("Y Axis:")
        tab.yAxisLeft = qt.QRadioButton("left")
        tab.yAxisRight = qt.QRadioButton("right")
        layout4.addWidget(tab.yAxisLabel)
        layout4.addWidget(tab.yAxisLeft)
        layout4.addWidget(tab.yAxisRight)
        layout4.addStretch()

        layout = qt.QVBoxLayout()
        layout.addLayout(layout3)
        layout.addLayout(layout2)
        layout.addLayout(layout4)
        tab.setLayout(layout)
        return tab

    def initColorOption(self, policy):
        if policy == gco.COLOR_POLICY_INDIVIDUAL:
            self.colorIndividual.setChecked(True)
        elif policy == gco.COLOR_POLICY_LOOP1:
            self.colorLoop1.setChecked(True)
        elif policy == gco.COLOR_POLICY_LOOP2:
            self.colorLoop2.setChecked(True)
        elif policy == gco.COLOR_POLICY_GRADIENT:
            self.colorGradient.setChecked(True)
        else:
            raise ValueError("wrong choice of color type")

    def setUIFromData(self):
        gpd.setRButtonGroupFromData(
            self.colorRadioButtons, 'parentItem.colorPolicy')
        color = gpd.getCommonPropInSelectedItems('color')
        self.color = color if color is not None else 'black'
        for tab in self.tabs:
            tab.color = self.color
        self.colorIndividualButton.colorCycle = [self.color]

        if len(csi.selectedItems) == 0:
            return
        parentItem = csi.selectedItems[0].parentItem
        if hasattr(parentItem, "color1"):
            self.color1 = parentItem.color1
        else:
            self.color1 = csi.selectedItems[0].color
        if hasattr(parentItem, "color2"):
            self.color2 = parentItem.color2
        else:
            self.color2 = csi.selectedItems[-1].color
        self.colorGradientButton.colorCycle = \
            gco.makeGradientCollection(self.color1, self.color2)

        item = csi.selectedTopItems[0]
        if hasattr(item, 'colorAutoUpdate'):
            cond = item.colorAutoUpdate
        else:
            cond = item.parentItem.colorAutoUpdate
        self.colorAutoCollective.setChecked(cond)

        if self.node.columnCount == 0:
            return
        for yName, tab in zip(self.node.plotYArrays, self.tabs):
            lineStyle = gpd.getCommonPropInSelectedItems(
                ['plotProps', self.node.name, yName, 'linestyle'])
            if lineStyle is not None:
                tab.styleComboBox.setCurrentIndex(
                    tuple(lineStylesText.values()).index(lineStyle))
            else:
                defaultIndex = tab.styleComboBox.count() - 1
                tab.styleComboBox.setCurrentIndex(defaultIndex)

            gpd.setSpinBoxFromData(
                tab.widthSpinBox,
                ['plotProps', self.node.name, yName, 'linewidth'])

            symbol = gpd.getCommonPropInSelectedItems(
                ['plotProps', self.node.name, yName, 'symbol'])
            if not symbol or (symbol in noSymbols):
                symbol = 'None'
            ind = tuple(lineSymbolsText.values()).index(symbol)
            tab.symbolComboBox.setCurrentIndex(ind)
            self.comboBoxChanged(tab, 'size', ind)

            gpd.setSpinBoxFromData(
                tab.sizeSpinBox,
                ['plotProps', self.node.name, yName, 'symbolsize'])

            axisY = gpd.getCommonPropInSelectedItems(
                ['plotProps', self.node.name, yName, 'yaxis'])
            if axisY is not None:
                if isinstance(axisY, type("")):
                    axisY = -1 if axisY.startswith("l") else 1
                tab.yAxisLeft.setChecked(axisY == -1)
                tab.yAxisRight.setChecked(axisY != -1)
            else:
                for rb in (tab.yAxisLeft, tab.yAxisRight):
                    rb.setAutoExclusive(False)
                    rb.setChecked(False)
                    rb.setAutoExclusive(True)

    def setButtonColor(self, color, policy):
        if policy == gco.COLOR_POLICY_INDIVIDUAL:
            self.color = color
            self.colorIndividualButton.colorCycle = [color]
        elif policy == gco.COLOR_POLICY_GRADIENT:
            if self.colorSeq % 2 == 0:
                self.color1 = color
            else:
                self.color2 = color
            colorCycle = gco.makeGradientCollection(self.color1, self.color2)
            self.colorGradientButton.colorCycle = colorCycle
        else:
            raise ValueError("wrong choice of color type")

    def openColorDialog(self, policy):
        title = 'Select Color'
        self.initColorOption(policy)
        if policy == gco.COLOR_POLICY_INDIVIDUAL:
            initialColor = self.color
        elif policy == gco.COLOR_POLICY_GRADIENT:
            if self.colorSeq % 2 == 0:
                initialColor = self.color1
                title += ' 1'
            else:
                initialColor = self.color2
                title += ' 2'
        else:
            return

        initialColor = qt.QColor(initialColor)
        color = qt.QColorDialog.getColor(
            title=title, parent=self, initial=initialColor,
            options=qt.QColorDialog.ShowAlphaChannel)
        if color.isValid():
            self.setButtonColor(color, policy)
            if policy == gco.COLOR_POLICY_GRADIENT:
                self.colorSeq += 1
            for tab in self.tabs:
                tab.color = color

    def updateFromSpinBox(self, tab, what):
        if what == "size":
            tab.symbolComboBox.repaint()
        elif what == "width":
            tab.styleComboBox.repaint()

    def comboBoxChanged(self, tab, what, ind):
        if what == "size":
            tab.sizeLabel.setVisible(ind != 0)
            tab.sizeSpinBox.setVisible(ind != 0)
        elif what == "width":
            tab.widthLabel.setVisible(ind != 0)
            tab.widthSpinBox.setVisible(ind != 0)

    def setColorOptions(self):
        def delColorIndividual(item):
            try:
                del item.colorIndividual
            except AttributeError:
                pass

        if self.colorIndividual.isChecked():
            policy = gco.COLOR_POLICY_INDIVIDUAL
        elif self.colorLoop1.isChecked():
            policy = gco.COLOR_POLICY_LOOP1
        elif self.colorLoop2.isChecked():
            policy = gco.COLOR_POLICY_LOOP2
        elif self.colorGradient.isChecked():
            policy = gco.COLOR_POLICY_GRADIENT
        else:
            return

        parentItem = None
        if self.isGroupSelected:
            parentItem = csi.selectedTopItems[0]
        elif self.isTopGroupSelected:
            parentItem = csi.dataRootItem
        if parentItem:
            parentItem.colorPolicy = policy

        if policy == gco.COLOR_POLICY_INDIVIDUAL:
            colorn = gco.getColorName(self.color)
            if parentItem:
                parentItem.color = colorn
            else:
                for item in csi.selectedItems:
                    item.colorIndividual = colorn
                    item.color = colorn
        elif policy == gco.COLOR_POLICY_LOOP1:
            if parentItem:
                for item in parentItem.childItems:
                    delColorIndividual(item)
            else:
                for i, item in enumerate(csi.selectedItems):
                    color = gco.colorCycle1[i % len(gco.colorCycle1)]
                    item.color = color
        elif policy == gco.COLOR_POLICY_LOOP2:
            if parentItem:
                for item in parentItem.childItems:
                    delColorIndividual(item)
            else:
                for i, item in enumerate(csi.selectedItems):
                    color = gco.colorCycle2[i % len(gco.colorCycle2)]
                    item.color = color
        elif policy == gco.COLOR_POLICY_GRADIENT:
            if parentItem:
                parentItem.color1 = self.color1
                parentItem.color2 = self.color2
                for item in parentItem.childItems:
                    delColorIndividual(item)
            else:
                colorCycle = gco.makeGradientCollection(
                    self.color1, self.color2)
                for item, color in zip(csi.selectedItems, colorCycle):
                    item.color = color

        if parentItem:
            parentItem.init_colors(parentItem.childItems)

    def setLineOptions(self):
        for yName, tab in zip(self.node.plotYArrays, self.tabs):
            props = {}
            txt = tab.symbolComboBox.currentText()
            if cco.str_not_blank(txt):
                props['symbol'] = lineSymbolsText[txt]
            txt = tab.sizeSpinBox.text()
            if cco.str_not_blank(txt):
                props['symbolsize'] = tab.sizeSpinBox.value()
            txt = tab.styleComboBox.currentText()
            if cco.str_not_blank(txt):
                props['linestyle'] = lineStylesText[txt]
            txt = tab.widthSpinBox.text()
            if cco.str_not_blank(txt):
                props['linewidth'] = tab.widthSpinBox.value()
            if tab.yAxisLeft.isChecked() or tab.yAxisRight.isChecked():
                props['yaxis'] = 'left' if tab.yAxisLeft.isChecked() else \
                    'right'
            for item in csi.selectedItems:
                lineProps = item.plotProps[self.node.name][yName]
                for prop in props:
                    lineProps[prop] = props[prop]
        if csi.model is not None:  # can be None in dialog test
            csi.model.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
        return lineProps

    def accept(self):
        self.setColorOptions()
        self.setLineOptions()
        try:  # self.node.widget may be None in tests
            self.node.widget.replot()
        except Exception:
            pass
        super().accept()
