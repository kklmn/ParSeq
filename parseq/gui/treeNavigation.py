# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "4 Nov 2026"

from silx.gui import qt


class TreeNavigatorSlider(qt.QSlider):
    CENTER = 100

    def __init__(self, tree, parent=None):
        super().__init__(qt.Qt.Vertical, parent)
        self.setToolTip('navigate selection')
        self.tree = tree
        self.setRange(0, 2*self.CENTER)
        self.setValue(self.CENTER)

        self.setInvertedAppearance(True)
        self.setFocusPolicy(qt.Qt.NoFocus)

        self.setStyleSheet("""
            QSlider:vertical {
                width: 18px;
            }
            QSlider::groove:vertical {
                background: palette(mid);
                width: 4px;
                border-radius: 2px;
                margin: 12px 0;
            }
            QSlider::handle:vertical {
                background: palette(highlight);
                width: 12px;
                height: 12px;
                margin: -2px -7px;
                border-radius: 5px;
                border: 1px solid palette(dark);
            }
            QSlider::handle:vertical:hover {
                background: #4da3ff;
            }
            QSlider::handle:vertical:pressed {
                background: #2d7bd7;
            }
            """)

        self.timer = qt.QTimer(self)
        self.timer.timeout.connect(self.navigate)
        self.sliderPressed.connect(self.startNavigation)
        self.sliderReleased.connect(self.stopNavigation)

        self.actionTriggered.connect(self.onAction)

    def onAction(self, action):
        if action == self.SliderPageStepAdd:
            self.setValue(self.CENTER)
        elif action == self.SliderPageStepSub:
            self.setValue(self.CENTER)

    def startNavigation(self):
        self.timer.start(30)  # ms

    def stopNavigation(self):
        self.timer.stop()
        self.setValue(self.CENTER)

    def navigate(self):
        delta = self.value() - self.CENTER
        if delta == 0:
            return
        idx = self.tree.currentIndex()
        if not idx.isValid():
            idx = self.tree.indexAt(self.tree.viewport().rect().center())
        if not idx.isValid():
            return

        speed = max(1, abs(delta) // 10)
        if delta > 0:
            for _ in range(speed):
                nxt = self.tree.indexBelow(idx)
                if not nxt.isValid():
                    break
                idx = nxt
        else:
            for _ in range(speed):
                prv = self.tree.indexAbove(idx)
                if not prv.isValid():
                    break
                idx = prv

        selModel = self.tree.selectionModel()
        selModel.setCurrentIndex(idx, selModel.ClearAndSelect | selModel.Rows)
        self.tree.scrollTo(idx, qt.QAbstractItemView.PositionAtCenter)
