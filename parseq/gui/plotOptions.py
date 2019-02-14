# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from collections import OrderedDict
from functools import partial
from silx.gui import qt

lineStyles = {
    None: qt.Qt.NoPen,
    'None': qt.Qt.NoPen,
    'none': qt.Qt.NoPen,
    '': qt.Qt.NoPen,
    ' ': qt.Qt.NoPen,
    '-': qt.Qt.SolidLine,
    '--': qt.Qt.DashLine,
    ':': qt.Qt.DotLine,
    '-.': qt.Qt.DashDotLine
}

lineStylesText = OrderedDict([
    ('no line', ' '), ('solid', '-'), ('dashed', '--'), ('dash-dot', '-.'),
    ('dotted', ':')])

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

noSymbols = (None, 'None', 'none', '', ' ')

lineSymbolsText = OrderedDict([
    ('no symbol', ''), ('circle', 'o'), ('point', '.'), ('pixel', ','),
    ('cross', '+'), ('x-cross', 'x'), ('diamond', 'd'), ('square', 's')])


class LineStyleDelegate(qt.QItemDelegate):
    def paint(self, painter, option, index):
        txt = index.model().data(index, qt.Qt.DisplayRole)
        if txt.startswith('no'):
            super(LineStyleDelegate, self).paint(painter, option, index)
            return
        lineStyle = lineStyles[lineStylesText[txt]]
        painter.save()
        rect = option.rect
        rect.adjust(+5, 0, -5, 0)
        pen = qt.QPen()
        pen.setColor(qt.QColor(self.parent().color))
        pen.setWidth(self.parent().widthSpinBox.value())
        pen.setStyle(lineStyle)
        painter.setPen(pen)
        middle = (rect.bottom() + rect.top()) / 2
        painter.drawLine(rect.left(), middle, rect.right(), middle)
        painter.restore()


class LineStyleComboBox(qt.QComboBox):
    def paintEvent(self, e):
        txt = self.currentText()
        if txt.startswith('no'):
            super(LineStyleComboBox, self).paintEvent(e)
            return
        lineStyle = lineStyles[lineStylesText[txt]]
        p = qt.QStylePainter(self)
        p.setPen(self.palette().color(qt.QPalette.Text))
        opt = qt.QStyleOptionComboBox()
        self.initStyleOption(opt)
        p.drawComplexControl(qt.QStyle.CC_ComboBox, opt)
        painter = qt.QPainter(self)
        painter.save()
        rect = p.style().subElementRect(
            qt.QStyle.SE_ComboBoxFocusRect, opt, self)
        rect.adjust(+5, 0, -5, 0)
        pen = qt.QPen()
        pen.setColor(qt.QColor(self.parent().color))
        pen.setWidth(self.parent().widthSpinBox.value())
        pen.setStyle(lineStyle)
        painter.setPen(pen)
        middle = (rect.bottom() + rect.top()) / 2
        painter.drawLine(rect.left(), middle, rect.right(), middle)
        painter.restore()


class SymbolDelegate(qt.QItemDelegate):
    def paint(self, painter, option, index):
        txt = index.model().data(index, qt.Qt.DisplayRole)
        if txt.startswith('no'):
            super(SymbolDelegate, self).paint(painter, option, index)
            return
        lineSymbol = lineSymbols[lineSymbolsText[txt]]
        painter.save()
        rect = option.rect
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


class SymbolComboBox(qt.QComboBox):
    def paintEvent(self, e):
        txt = self.currentText()
        if txt.startswith('no'):
            super(SymbolComboBox, self).paintEvent(e)
            return
        lineSymbol = lineSymbols[lineSymbolsText[txt]]
        p = qt.QStylePainter(self)
        p.setPen(self.palette().color(qt.QPalette.Text))
        opt = qt.QStyleOptionComboBox()
        self.initStyleOption(opt)
        p.drawComplexControl(qt.QStyle.CC_ComboBox, opt)
        painter = qt.QPainter(self)
        painter.save()
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


class LineProps(qt.QDialog):
    def __init__(self, parent, node, activeTab=None):
        super(LineProps, self).__init__(parent)

        self.tabWidget = qt.QTabWidget()
        self.tabs = []
        yNs = node.yQLabels if hasattr(node, "yQLabels") else node.yNames
        self.tabs = []
        for yN in yNs:
            tab = qt.QWidget()
            tab.color = 'k'
            self.tabWidget.addTab(tab, yN)
            self.tabUI(tab)
            self.tabs.append(tab)
        self.setWindowTitle("Line properties")
        mainLayout = qt.QVBoxLayout()
        mainLayout.addWidget(self.tabWidget)
        buttonBox = qt.QDialogButtonBox(
            qt.QDialogButtonBox.Ok | qt.QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)  # OK button
        buttonBox.rejected.connect(self.reject)  # Cancel button
        mainLayout.addStretch()
        mainLayout.addWidget(buttonBox)
        self.setLayout(mainLayout)
        self.setSizePolicy(qt.QSizePolicy.Minimum, qt.QSizePolicy.Minimum)
        if activeTab is not None:
            self.tabWidget.setCurrentIndex(activeTab)

    def tabUI(self, tab):
        layout1 = qt.QHBoxLayout()
        layout1.addWidget(qt.QLabel('Color:'))
        tab.colorButton = qt.QPushButton()
        tab.colorButton.clicked.connect(partial(self.openColorDialog, tab))
        layout1.addWidget(tab.colorButton, 1)

        layout2 = qt.QHBoxLayout()
        layout2.addWidget(qt.QLabel('Symbol:'))
        tab.symbolComboBox = SymbolComboBox(tab)
        symbolDelegate = SymbolDelegate(tab)
        tab.symbolComboBox.setItemDelegate(symbolDelegate)
        for symbol in tuple(lineSymbolsText.keys()):
            tab.symbolComboBox.addItem(symbol)
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
        layout2.addWidget(tab.sizeSpinBox, 1)

        layout3 = qt.QHBoxLayout()
        layout3.addWidget(qt.QLabel('Style:'))
        tab.styleComboBox = LineStyleComboBox(tab)
        lineStyleDelegate = LineStyleDelegate(tab)
        tab.styleComboBox.setItemDelegate(lineStyleDelegate)
        for style in tuple(lineStylesText.keys()):
            tab.styleComboBox.addItem(style)
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
        layout3.addWidget(tab.widthSpinBox, 1)

        layout = qt.QVBoxLayout(tab)
        layout.addLayout(layout1)
        layout.addLayout(layout2)
        layout.addLayout(layout3)
        tab.setLayout(layout)
#        self.setFixedSize(vLayout.minimumSize())

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

    def setColor(self, tab, color):
        tab.color = color
        tab.colorButton.setStyleSheet("background-color: %s" % color)

    def openColorDialog(self, tab):
        color = qt.QColorDialog().getColor()
        if color.isValid():
            self.setColor(tab, str(color.name()))

    def setLineProperties(self, tabInd=0, color=None, symbol=None,
                          symbolsize=5, style=None, width=1):
        tab = self.tabs[tabInd]
        if color is not None:
            self.setColor(tab, color)

        if symbol is not None:
            assert symbol in lineSymbolsText.values()
            index = list(lineSymbolsText.values()).index(symbol)
            tab.symbolComboBox.setCurrentIndex(index)
            self.comboBoxChanged(tab, "size", index)

        if symbolsize < tab.sizeSpinBox.minimum():
            symbolsize = tab.sizeSpinBox.minimum()
        if symbolsize > tab.sizeSpinBox.maximum():
            symbolsize = tab.sizeSpinBox.maximum()
        tab.sizeSpinBox.setValue(symbolsize)

        if style is not None:
            assert style in lineStylesText.values()
            index = list(lineStylesText.values()).index(style)
            tab.styleComboBox.setCurrentIndex(index)
            self.comboBoxChanged(tab, "width", index)

        if width < tab.widthSpinBox.minimum():
            width = tab.widthSpinBox.minimum()
        if width > tab.widthSpinBox.maximum():
            width = tab.widthSpinBox.maximum()
        tab.widthSpinBox.setValue(width)

    def getLineProperties(self, tabInd=0):
        tab = self.tabs[tabInd]
        properties = {
            'color': tab.color,
            'symbol': lineSymbolsText[tab.symbolComboBox.currentText()],
            'symbolsize': tab.sizeSpinBox.value(),
            'linestyle': lineStylesText[tab.styleComboBox.currentText()],
            'linewidth': tab.widthSpinBox.value()
            }
        return properties
