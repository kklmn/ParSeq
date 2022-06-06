import sys
from silx.gui import qt

import sys; sys.path.append('../..')  # analysis:ignore
import parseq.gui.gcommons as gco


class Window(qt.QWidget):
    def __init__(self):
        super().__init__()

        flow_layout = gco.FlowLayout(self)
        flow_layout.addWidget(qt.QPushButton("Short"))
        flow_layout.addWidget(qt.QPushButton("Longer"))
        flow_layout.addWidget(qt.QPushButton("Different text"))
        flow_layout.addWidget(qt.QPushButton("More text"))
        flow_layout.addWidget(qt.QPushButton("Even longer button text"))

        self.setWindowTitle("Flow Layout")


if __name__ == "__main__":
    app = qt.QApplication(sys.argv)
    main_win = Window()
    main_win.show()
    sys.exit(app.exec())
