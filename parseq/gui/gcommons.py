# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "19 Jul 2022"
# !!! SEE CODERULES.TXT !!!

import numpy as np
from silx.gui import qt, icons

colorCycle1 = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
               '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']  # mpl
colorCycle2 = ['#0000ff', '#00ee00', '#ff0000', '#00ffff', '#ff00ff',
               '#ffff00', '#aaaaaa', '#000000']

COLOR_POLICY_INDIVIDUAL, COLOR_POLICY_LOOP1, COLOR_POLICY_LOOP2,\
    COLOR_POLICY_GRADIENT = range(4)
COLOR_POLICY_NAMES = 'individual', 'loop1', 'loop2', 'gradient'

COLOR_HDF5_HEAD = '#2299f0'
COLOR_FS_COLUMN_FILE = '#32aa12'
COLOR_LOAD_CAN = '#44c044'
COLOR_LOAD_CANNOT = '#d03333'
COLOR_UNDEFINED = '#ff160c'
COLOR_ROI = '#f7b43e'
COLOR_COMBINED = '#ff00ff'

GROUP_COLOR = qt.QColor('#f4f0f0')
BUSY_COLOR_BGND = qt.QColor('#ffe9a1')
BUSY_COLOR_FGND = qt.QColor('#aaaa00')
BAD_COLOR = qt.QColor('#f47070')
UNDEFINED_COLOR = qt.QColor('#cccccc')
NOTFOUND_COLOR = qt.QColor('#ff88ff')
MATHERROR_COLOR = qt.QColor('#ffa500')

LIMITS_ROLE = qt.Qt.UserRole + 1


def getFormatStr(step):
    if 0.1 <= step < 1:
        return '{0:.1f}'
    elif 0.01 <= step < 0.1:
        return '{0:.2f}'
    elif 0.001 <= step < 0.01:
        return '{0:.3f}'
    elif 0.0001 <= step < 0.001:
        return '{0:.4f}'
    elif 0.00001 <= step < 0.0001:
        return '{0:.5f}'
    elif 0.000001 <= step < 0.00001:
        return '{0:.6f}'
    elif 0.0000001 <= step < 0.000001:
        return '{0:.7f}'
    elif 0.00000001 <= step < 0.0000001:
        return '{0:.8f}'
    else:
        return '{0}'


def getDecimals(step):
    if 0.1 <= step < 1:
        return 1
    elif 0.01 <= step < 0.1:
        return 2
    elif 0.001 <= step < 0.01:
        return 3
    elif 0.0001 <= step < 0.001:
        return 4
    elif 0.00001 <= step < 0.0001:
        return 5
    elif 0.000001 <= step < 0.00001:
        return 6
    elif 0.0000001 <= step < 0.000001:
        return 7
    elif 0.00000001 <= step < 0.0000001:
        return 8
    else:
        return 0


def makeGradientCollection(color1, color2, ncolor=8):
    c1 = np.array(qt.QColor(color1).getHsvF())
    c2 = np.array(qt.QColor(color2).getHsvF())
    c1[c1 < 0] = 0  # for gray, getHsvF returns hue=-1 that is not accepted by fromHsv  # noqa
    c2[c2 < 0] = 0
    t = np.linspace(0, 1, ncolor)[:, np.newaxis]
    colors = c1*(1-t) + c2*t
    res = []
    for i in range(ncolor):
        res.append(qt.QColor.fromHsvF(*colors[i]))
    return res


def getColorName(color):
    return qt.QColor(color).name()


class CheckBoxDelegate(qt.QItemDelegate):
    """
    The standard checkbox (of items with Qt.ItemIsUserCheckable) without text
    draws an empty focus rectangle on the right of the checkbox. This delegate
    draws only a centered check box.
    """

    def __init__(self, parent=None):
        self.defSize = qt.QSize(
            qt.QApplication.style().pixelMetric(qt.QStyle.PM_IndicatorWidth),
            qt.QApplication.style().pixelMetric(qt.QStyle.PM_IndicatorHeight))
        super().__init__(parent)

    def paint(self, painter, option, index):
        left = option.rect.center().x() - self.defSize.width()//2
        top = option.rect.center().y() - self.defSize.height()//2
        rect = qt.QRect(left, top, self.defSize.width(), self.defSize.height())
        self.drawCheck(painter, option, rect, index.data(qt.Qt.CheckStateRole))

    def editorEvent(self, event, model, option, index):
        if event.type() == qt.QEvent.MouseButtonRelease:
            value = index.data(qt.Qt.CheckStateRole)
            model.setData(index, not value, qt.Qt.CheckStateRole)
            return True
        return super().editorEvent(event, model, option, index)


class MultiLineEditDelegate(qt.QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        edit = qt.QTextEdit(parent)
        edit.setVerticalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOff)
        return edit

    def setEditorData(self, editor, index):
        # editor.blockSignals(True)
        editor.setText(index.data())
        sbar = editor.verticalScrollBar()
        sbar.setValue(sbar.maximum())
        # editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.toPlainText())

    def eventFilter(self, editor, event):
        if (event.type() == qt.QEvent.KeyPress and
                event.key() == qt.Qt.Key_Return):
            self.commitData.emit(editor)
            if True:  # emit closeEditor
                self.closeEditor.emit(editor)
            else:  # select contents instead
                editor.selectAll()
            return True
        return False

    # def updateEditorGeometry(self, editor, option, index):
    #     editor.setGeometry(option.rect.x(), option.rect.y(),
    #                        option.rect.width(), option.rect.height()-10)


class DoubleSpinBoxDelegate(qt.QStyledItemDelegate):
    """
    This delegate ctreates a QDoubleSpinBox and sets its limits and step as got
    from the model's data with a role LIMITS_ROLE.
    """

    def __init__(self, parent, alignment):
        super().__init__(parent)
        self.alignment = alignment

    def createEditor(self, parent, option, index):
        dsb = qt.QDoubleSpinBox(parent)
        dsb.setAccelerated(True)
        limits = index.data(role=LIMITS_ROLE)
        if limits:
            dsb.setMinimum(float(limits[0]))
            dsb.setMaximum(float(limits[1]))
            step = limits[2]
            dsb.setSingleStep(step)
            decimals = getDecimals(step)
            dsb.setDecimals(decimals)
        dsb.setAlignment(self.alignment)
        dsb.valueChanged.connect(self.valueChanged)
        return dsb

    def valueChanged(self):
        self.commitData.emit(self.sender())

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect.x(), option.rect.y(),
                           option.rect.width(), option.rect.height()-1)


class RichTextPushButton(qt.QPushButton):
    def __init__(self, text, parent):
        super().__init__(parent)
        self.__lbl = qt.QLabel(self)
        self.lbl = self.__lbl
        self.__lbl.setText(text)
        self.__lyt = qt.QHBoxLayout()
        self.__lyt.setContentsMargins(4, 0, 0, 0)
        self.__lyt.setSpacing(0)
        self.setLayout(self.__lyt)
        # self.__lbl.setAttribute(qt.Qt.WA_TranslucentBackground)
        self.__lbl.setAttribute(qt.Qt.WA_TransparentForMouseEvents)
        self.__lbl.setSizePolicy(qt.QSizePolicy.Expanding,
                                 qt.QSizePolicy.Expanding)
        self.__lbl.setTextFormat(qt.Qt.RichText)
        self.__lyt.addWidget(self.__lbl)
        return

    def setText(self, text):
        self.__lbl.setText(text)
        self.updateGeometry()
        return

    def sizeHint(self):
        s = qt.QPushButton.sizeHint(self)
        w = self.__lbl.sizeHint()
        s.setWidth(w.width())
        s.setHeight(w.height())
        return s


class CloseButton(qt.QToolButton):
    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.setIcon(icons.getQIcon('remove'))
        self.setStyleSheet("QToolButton{border-radius: 8px;}"
                           "QToolButton:hover{background-color: #ffe0e6;}")


class StrLabelWithCloseButton(qt.QFrame):
    delete = qt.pyqtSignal(str)

    def __init__(self, parent, txt):
        super().__init__(parent)
        self.txt = txt

        txtLabel = qt.QLabel(txt)
        bbox = txtLabel.fontMetrics().boundingRect(txt)
        txtLabel.setFixedSize(bbox.width()+8, bbox.height()+2)
        txtLabel.setStyleSheet("QLabel{border-radius: 4px;}")

        closeButton = CloseButton(self)
        closeButton.setToolTip("remove this text field")
        closeButton.clicked.connect(self.__close)

        layout = qt.QHBoxLayout()
        layout.setContentsMargins(4, 0, 2, 1)
        layout.setSpacing(0)
        layout.addWidget(txtLabel)
        layout.addWidget(closeButton)
        self.setSizePolicy(qt.QSizePolicy.Minimum, qt.QSizePolicy.Minimum)
        self.setLayout(layout)

        self.setStyleSheet(
            "QFrame{background-color: white; border-radius: 4px;}")

    def __close(self, checked):
        self.delete.emit(self.txt)


class IntButtonWithCloseButton(qt.QFrame):
    gotoFrame = qt.pyqtSignal(int)
    deleteFrame = qt.pyqtSignal(int)

    def __init__(self, parent, key):
        super().__init__(parent)
        self.key = key

        txt = str(key)
        gotoButton = qt.QPushButton(txt)
        bbox = gotoButton.fontMetrics().boundingRect(txt)
        gotoButton.setFixedSize(bbox.width()+8, bbox.height()+2)
        gotoButton.setToolTip("go to the key frame")
        gotoButton.clicked.connect(self.__goto)
        gotoButton.setStyleSheet(
            "QPushButton{border-radius: 4px;}" +
            "QPushButton:hover{{background-color: {0};}}".format(COLOR_ROI))

        closeButton = CloseButton(self)
        closeButton.setToolTip("remove this key frame")
        closeButton.clicked.connect(self.__close)

        layout = qt.QHBoxLayout()
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(0)
        layout.addWidget(gotoButton)
        layout.addWidget(closeButton)
        self.setSizePolicy(qt.QSizePolicy.Minimum, qt.QSizePolicy.Minimum)
        self.setLayout(layout)

        self.setStyleSheet(
            "QFrame{background-color: white; border-radius: 4px;}")

    def __goto(self):
        self.gotoFrame.emit(self.key)

    def __close(self, checked):
        self.deleteFrame.emit(self.key)


class FlowLayout(qt.QLayout):
    """From
    doc.qt.io/qtforpython/examples/example_widgets_layouts_flowlayout.html"""

    def __init__(self, parent=None):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(qt.QMargins(0, 0, 0, 0))
            self.setSpacing(4)
        self._item_list = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._item_list.append(item)

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):
        return qt.Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self._do_layout(qt.QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = qt.QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        size += qt.QSize(2*self.contentsMargins().top(),
                         2*self.contentsMargins().top())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._item_list:
            style = item.widget().style()
            layout_spacing_x = style.layoutSpacing(
                qt.QSizePolicy.PushButton, qt.QSizePolicy.PushButton,
                qt.Qt.Horizontal)
            layout_spacing_y = style.layoutSpacing(
                qt.QSizePolicy.PushButton, qt.QSizePolicy.PushButton,
                qt.Qt.Vertical)
            space_x = spacing + layout_spacing_x
            space_y = spacing + layout_spacing_y
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(qt.QRect(qt.QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y()


class QVBoxLayoutAbove(qt.QVBoxLayout):
    def addExtraWidget(self, widget):
        """The widget must be given a parent (a group box)! """
        self.extraWidget = widget

    def setGeometry(self, rect):
        super().setGeometry(rect)
        size = self.extraWidget.sizeHint()
        w, h = size.width(), size.height()
        x, y = rect.right()-w-2, rect.y()-h+1
        self.extraWidget.setGeometry(qt.QRect(x, y, w, h))


class StateButtons(qt.QFrame):
    statesActive = qt.pyqtSignal(list)

    def __init__(self, parent, caption, names, active=None, default=None):
        """
        *names*: a list of any objects that will be displayed as str(object),

        *active*: a subset of names that will be displayed as checked,

        *caption* will be displayed as QLabel in front of all state buttons.

        *default* if not None, is an object from *names* that will be checked
                  when all buttons are unchecked, so that there is always at
                  least one checked.

        The signal *statesActive* is emitted on pressing a button. It sends a
        list of selected names, as a subset of *names*.
        """
        super().__init__(parent)
        self.names = names
        self.default = default

        self.buttons = []
        layout = FlowLayout()
        if caption is not None:
            label = qt.QLabel(caption)
            layout.addWidget(label)
        # styleSheet = "QPushButton{border-radius: 4px;}" +\
        #     "QPushButton{background-color: lightsalmon;}" +\
        #     "QPushButton:checked{background-color: lightgreen;}" +\
        #     "QPushButton:hover{{background-color: {0};}}".format(COLOR_ROI)
        styleSheet = """
        QPushButton {
            border-style: outset;
            border-width: 2px;
            border-radius: 5px;
            border-color: lightsalmon;}
        QPushButton:checked {
            border-style: inset;
            border-width: 2px;
            border-radius: 5px;
            border-color: lightgreen;}
        QPushButton:hover {
            border-style: solid;
            border-width: 2px;
            border-radius: 5px;
            border-color: lightblue;}
        """
        for name in names:
            strName = str(name)
            but = qt.QPushButton(strName)
            but.setCheckable(True)

            bbox = but.fontMetrics().boundingRect(strName)
            but.setFixedSize(bbox.width()+12, bbox.height()+4)
            # but.setToolTip("go to the key frame")
            but.clicked.connect(self.buttonClicked)
            but.setStyleSheet(styleSheet)

            self.buttons.append(but)
            layout.addWidget(but)
        self.setLayout(layout)

        self.setActive(active)

    def getActive(self):
        res = [name for (button, name) in
               zip(self.buttons, self.names) if button.isChecked()]
        if len(res) == 0 and self.default is not None:
            res = [self.default]
            self.setActive(res)
        return res

    def setActive(self, active):
        if not isinstance(active, (list, tuple)):
            return
        for button, name in zip(self.buttons, self.names):
            button.setChecked(name in active)

    def buttonClicked(self, checked):
        self.statesActive.emit(self.getActive())


class EDoubleSpinBox(qt.QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        self.strFormat = kwargs.pop('strFormat', '{0:.2g}')
        super().__init__(*args, **kwargs)
        self.setMinimum(-np.inf)
        self.setMaximum(np.inf)

    def validate(self, strn, pos):
        try:
            float(strn)
        except Exception:
            ret = qt.QValidator.State.Invalid
        else:
            ret = qt.QValidator.State.Acceptable
        return (ret, strn, pos)

    def textFromValue(self, value):
        string = self.strFormat.format(value).replace("e+0", "e")\
            .replace("e-0", "e-")
        return string

    def valueFromText(self, string):
        if string == "":
            return self.value()
        try:
            value = float(string)
        except Exception:
            return

        if value > self.maximum():
            value = self.maximum()
        if value < self.minimum():
            value = self.minimum()
        return value

    def stepBy(self, steps):
        txt = self.cleanText()
        pos = txt.find('e')
        try:
            digit = int(txt[pos-1])
            digit += -1 if digit == 9 else 1
            ltxt = list(txt)
            ltxt[pos-1] = str(digit)
            increment = abs(float(txt) - float("".join(ltxt)))
        except Exception:
            return

        val = self.valueFromText(txt)
        newStr = self.textFromValue(val + steps*increment)
        self.lineEdit().setText(newStr)
        self.setValue(val + steps*increment)
