# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import sys
from functools import partial
from silx.gui import qt
from ...gui.propWidget import PropWidget
from ...gui import propsOfData as gpd


class QLimitButton(qt.QPushButton):
    def paintEvent(self, event):
        painter = qt.QStylePainter(self)
        painter.rotate(270)
        painter.translate(-self.height(), 0)
        painter.drawControl(qt.QStyle.CE_PushButton, self.getStyleOptions())

    def getStyleOptions(self):
        options = qt.QStyleOptionButton()
        options.initFrom(self)
        size = options.rect.size()
        size.transpose()
        options.rect.setSize(size)
        try:
            options.features = qt.QStyleOptionButton.None_
        except AttributeError:
            options.features = getattr(qt.QStyleOptionButton, 'None')
        if self.isDown():
            options.state |= qt.QStyle.State_Sunken
        else:
            options.state |= qt.QStyle.State_Raised
        options.text = self.text()
        return options


class QSpinBoxLim(qt.QFrame):
    def __init__(self, SpinBoxClass, v, minV, maxV, decimals, step,
                 limitButtons=''):
        super(QSpinBoxLim, self).__init__()
        self.spinBox = SpinBoxClass()
        if isinstance(minV, (int, float)):
            self.spinBox.setMinimum(minV)
            self.getMinimum = None
        elif callable(minV):
            self.getMinimum = minV
        if isinstance(maxV, (int, float)):
            self.spinBox.setMaximum(maxV)
            self.getMaximum = None
        elif callable(maxV):
            self.getMaximum = maxV
        self.spinBox.setDecimals(decimals)
        self.spinBox.setSingleStep(step)
        if isinstance(v, type('')):
            self.spinBox.lineEdit().setText(v)
        else:
            self.spinBox.setValue(v)

        layout = qt.QHBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)
        layout.addWidget(self.spinBox, 1)

        if limitButtons:
            layoutV = qt.QVBoxLayout()
            layoutV.setContentsMargins(0, 0, 0, 0)
            layoutV.setSpacing(0)
            fontSize = "18" if sys.platform == "darwin" else "14"

            self.limMax = QLimitButton(u'»')
            self.limMin = QLimitButton(u'«')
            for widg, lbl in zip([self.limMax, self.limMin], ["max", "min"]):
                widg.setStyleSheet("margin: 0; font: "+fontSize+"px")
                widg.setFixedWidth(15)
                widg.setFixedHeight(11)
                widg.clicked.connect(partial(self.setToLimit, lbl))
                sp = widg.sizePolicy()
                try:
                    sp.setRetainSizeWhenHidden(True)
                except AttributeError:
                    pass
                widg.setSizePolicy(sp)
                widg.setVisible(lbl in limitButtons.lower())
                layoutV.addWidget(widg, 0)

            layout.addLayout(layoutV)

        self.setLayout(layout)

    def setToLimit(self, lim):
        if lim == "min":
            if self.getMinimum is not None:
                value = self.getMinimum()
                self.spinBox.setMinimum(value)
            else:
                value = self.spinBox.minimum()
        elif lim == "max":
            if self.getMaximum is not None:
                value = self.getMaximum()
                self.spinBox.setMaximum(value)
            else:
                value = self.spinBox.maximum()
        else:
            raise ValueError("unknown use pattern")
        self.spinBox.setValue(value)


class Tr0Widget(PropWidget):
    def __init__(self, parent=None, transform=None):
        super(Tr0Widget, self).__init__(parent)
        self.transform = transform
        self.params = transform.params if transform is not None else {}

        layout = qt.QVBoxLayout()
        layout.setSpacing(2)
        layout.setContentsMargins(0, 0, 0, 0)

        self.calibrationPanel = qt.QGroupBox(self)
        self.calibrationPanel.setFlat(False)
        self.calibrationPanel.setTitle("energy calibration TODO")
        self.calibrationPanel.setCheckable(True)
        self.calibrationPanel.setChecked(False)
        self.calibrationPanel.toggled.connect(
            partial(self.updatePropFromCheckBox, "correctionNeeded"))

        layoutC = qt.QVBoxLayout()

        layoutT = qt.QHBoxLayout()
        typeLabel = qt.QLabel("type")
        layoutT.addWidget(typeLabel)
        self.typeCB = qt.QComboBox()
        self.typeCB.addItems(["not implemented"])
        layoutT.addWidget(self.typeCB, 1)
        layoutC.addLayout(layoutT)

        layoutR = qt.QHBoxLayout()
        refLabel = qt.QLabel("E ref")
        layoutR.addWidget(refLabel)
        self.eRef = QSpinBoxLim(
            qt.QDoubleSpinBox, self.params["Eref"], 0, 2e5, 3, 0.1)
        layoutR.addWidget(self.eRef)
        layoutC.addLayout(layoutR)

        layoutS = qt.QHBoxLayout()
        shiftLabel1 = qt.QLabel("E shift at")
        layoutS.addWidget(shiftLabel1)
        self.shiftAtCB = qt.QComboBox()
        layoutS.addWidget(self.shiftAtCB)
        shiftLabel2 = qt.QLabel("=")
        layoutS.addWidget(shiftLabel2)
        self.shift = qt.QLabel("0.000")
        layoutS.addWidget(self.shift)
        layoutS.addStretch()
        layoutC.addLayout(layoutS)

        self.calibrationPanel.setLayout(layoutC)

        layout.addWidget(self.calibrationPanel)
        layout.addStretch()
        self.setLayout(layout)

    def setUIFromData(self):
        pass


class Tr1Widget(PropWidget):
    def __init__(self, parent=None, transform=None):
        super(Tr1Widget, self).__init__(parent)
        self.transform = transform
        self.params = transform.params if transform is not None else {}

        layout = qt.QVBoxLayout()
        layout.setSpacing(2)
        layout.setContentsMargins(0, 0, 0, 0)

        layoutL = qt.QHBoxLayout()
        paramLabel = qt.QLabel("E0 =")
        layoutL.addWidget(paramLabel)
        self.e0DSB = QSpinBoxLim(
            qt.QDoubleSpinBox, self.params["E0"], 0, 2e5, 1, 0.2)
        self.e0DSB.spinBox.valueChanged.connect(
            partial(self.updatePropFromSpinBox, "E0"))
        layoutL.addWidget(self.e0DSB, 0)
        layoutL.addStretch()
        layout.addLayout(layoutL)

        layoutL = qt.QHBoxLayout()
        paramLabel = qt.QLabel("kmin =")
        layoutL.addWidget(paramLabel)
        self.kminDSB = QSpinBoxLim(
            qt.QDoubleSpinBox, self.params["kmin"], 0, 50, 2, 0.1,
            limitButtons='min')
        self.kminDSB.spinBox.valueChanged.connect(
            partial(self.updatePropFromSpinBox, "kmin"))
        layoutL.addWidget(self.kminDSB, 1)

        paramLabel = qt.QLabel("kmax =")
        layoutL.addWidget(paramLabel)
        self.kmaxDSB = QSpinBoxLim(
            qt.QDoubleSpinBox, self.params["kmax"], 0, self.transform.get_kmax,
            2, 0.1, limitButtons='max')
        self.kmaxDSB.spinBox.valueChanged.connect(
            partial(self.updatePropFromSpinBox, "kmax"))
        layoutL.addWidget(self.kmaxDSB, 1)

        paramLabel = qt.QLabel("dk =")
        layoutL.addWidget(paramLabel)
        self.dkDSB = QSpinBoxLim(
            qt.QDoubleSpinBox, self.params["dk"], 0.01, 1, 3, 0.005)
        self.dkDSB.spinBox.valueChanged.connect(
            partial(self.updatePropFromSpinBox, "dk"))
        layoutL.addWidget(self.dkDSB, 1)
        layout.addLayout(layoutL)

        layoutL = qt.QHBoxLayout()
        paramLabel = qt.QLabel("smoothing =")
        layoutL.addWidget(paramLabel)
        self.smDSB = QSpinBoxLim(
            qt.QDoubleSpinBox, self.params["smoothing"], 0, 2e5, 1, 0.2)
        self.smDSB.spinBox.valueChanged.connect(
            partial(self.updatePropFromSpinBox, "smoothing"))
        layoutL.addWidget(self.smDSB, 0)
        layoutL.addStretch()
        layout.addLayout(layoutL)

        layoutL = qt.QHBoxLayout()
        paramLabel = qt.QLabel(u"×k<sup>w</sup>, w =")
        layoutL.addWidget(paramLabel)
        self.kwCB = qt.QComboBox()
        self.kwCB.addItems(['', '1', '2', '3'])
        self.kwCB.currentIndexChanged.connect(
            partial(self.updatePropFromComboBox, "kw"))
        layoutL.addWidget(self.kwCB, 0)
        layoutL.addStretch()
        layout.addLayout(layoutL)

        layout.addStretch()
        self.setLayout(layout)

    def setUIFromData(self):
        tname = self.transform.name
        gpd.setSpinBoxFromData(
            self.e0DSB.spinBox, ['transformParams', tname, 'E0'])
        gpd.setSpinBoxFromData(
            self.kminDSB.spinBox, ['transformParams', tname, 'kmin'])
        gpd.setSpinBoxFromData(
            self.kmaxDSB.spinBox, ['transformParams', tname, 'kmax'])
        gpd.setSpinBoxFromData(
            self.dkDSB.spinBox, ['transformParams', tname, 'dk'])
        gpd.setSpinBoxFromData(
            self.smDSB.spinBox, ['transformParams', tname, 'smoothing'])
        gpd.setComboBoxFromData(self.kwCB, ['transformParams', tname, 'kw'])


class Tr2Widget(PropWidget):
    def __init__(self, parent=None, transform=None):
        super(Tr2Widget, self).__init__(parent)
        self.transform = transform
        self.params = transform.params if transform is not None else {}

        layout = qt.QVBoxLayout()

        layoutL = qt.QHBoxLayout()
        paramLabel = qt.QLabel("rmax =")
        layoutL.addWidget(paramLabel)
        self.rmaxDSB = QSpinBoxLim(
            qt.QDoubleSpinBox, self.params["rmax"], 0., 50., 2, 0.1)
        self.rmaxDSB.spinBox.valueChanged.connect(
            partial(self.updatePropFromSpinBox, "rmax"))
        layoutL.addWidget(self.rmaxDSB, 1)
        layout.addLayout(layoutL)

        layout.addStretch()
        self.setLayout(layout)

    def setUIFromData(self):
        gpd.setSpinBoxFromData(
            self.rmaxDSB.spinBox,
            ['transformParams', self.transform.name, 'rmax'])
