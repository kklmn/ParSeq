# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

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


class LineProps(qt.QDialog):
    def __init__(self, parent, node):
        super(LineProps, self).__init__(parent)

        self.tabWidget = qt.QTabWidget()
        self.tabs = []
        yNs = node.yQLabels if hasattr(node, "yQLabels") else node.yNames
        for yN in yNs:
            tab = qt.QWidget()
            self.tabWidget.addTab(tab, yN)
            self.tabUI(tab)
        self.setWindowTitle("Line properties")
        mainLayout = qt.QVBoxLayout()
        mainLayout.addWidget(self.tabWidget)
        self.setLayout(mainLayout)
        self.setSizePolicy(qt.QSizePolicy.Minimum, qt.QSizePolicy.Minimum)

    def tabUI(self, tab):
        layout = qt.QVBoxLayout()
        layout.addWidget(qt.QLabel("Not implemented yet"))
        tab.setLayout(layout)
