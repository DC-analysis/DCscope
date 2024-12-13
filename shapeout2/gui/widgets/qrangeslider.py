from PyQt6 import QtCore, QtGui, QtWidgets

DEFAULT_CSS = """
QRangeSlider * {
    border: 0px;
    padding: 0px;
}
QRangeSlider #Head {
    background: #cef;
}
QRangeSlider #Span {
    background: #16f;
}
QRangeSlider #Span:active {
    background: #05f;
}
QRangeSlider #Tail {
    background: #cef;
}
QRangeSlider > QSplitter::handle {
    background: #08f;
}
QRangeSlider > QSplitter::handle:vertical {
    height: 3px;
}
QRangeSlider > QSplitter::handle:pressed {
    background: #0cf;
}
"""


def scale(val, src, dst):
    ret = ((val - src[0]) / float(src[1]-src[0])) * (dst[1]-dst[0]) + dst[0]
    return int(ret)


class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName("QRangeSlider")
        Form.setStyleSheet(DEFAULT_CSS)
        self.gridLayout = QtWidgets.QGridLayout(Form)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setSpacing(0)
        self.gridLayout.setObjectName("gridLayout")
        self._splitter = QtWidgets.QSplitter(Form)
        self._splitter.setMinimumSize(QtCore.QSize(0, 0))
        self._splitter.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self._splitter.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self._splitter.setObjectName("splitter")
        self._head = QtWidgets.QGroupBox(self._splitter)
        self._head.setTitle("")
        self._head.setObjectName("Head")
        self._handle = QtWidgets.QGroupBox(self._splitter)
        self._handle.setTitle("")
        self._handle.setObjectName("Span")
        self._tail = QtWidgets.QGroupBox(self._splitter)
        self._tail.setTitle("")
        self._tail.setObjectName("Tail")
        self.gridLayout.addWidget(self._splitter, 0, 0, 1, 1)
        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        _translate = QtCore.QCoreApplication.translate
        Form.setWindowTitle(_translate("QRangeSlider", "QRangeSlider"))


class Element(QtWidgets.QGroupBox):
    def __init__(self, parent, main, *args, **kwargs):
        super(Element, self).__init__(parent, *args, **kwargs)
        self.main = main

    def setStyleSheet(self, style):
        self.parent().setStyleSheet(style)

    def textColor(self):
        return getattr(self, '__textColor', QtGui.QColor(125, 125, 125))

    def setTextColor(self, color):
        if type(color) is tuple and len(color) == 3:
            color = QtGui.QColor(color[0], color[1], color[2])
        elif type(color) is int:
            color = QtGui.QColor(color, color, color)
        setattr(self, '__textColor', color)

    def paintEvent(self, event):
        qp = QtGui.QPainter()
        qp.begin(self)
        if self.main.drawValues():
            self.drawText(event, qp)
        qp.end()


class Head(Element):
    def __init__(self, parent, main, *args, **kwargs):
        super(Head, self).__init__(parent, main, *args, **kwargs)

    def drawText(self, event, qp):
        qp.setPen(self.textColor())
        qp.setFont(QtGui.QFont('Arial', 10))
        qp.drawText(event.rect(), QtCore.Qt.AlignmentFlag.AlignLeft,
                    str(self.main.min()))


class Tail(Element):
    def __init__(self, parent, main, *args, **kwargs):
        super(Tail, self).__init__(parent, main, *args, **kwargs)

    def drawText(self, event, qp):
        qp.setPen(self.textColor())
        qp.setFont(QtGui.QFont('Arial', 10))
        qp.drawText(event.rect(), QtCore.Qt.AlignmentFlag.AlignRight,
                    str(self.main.max()))


class Handle(Element):
    def __init__(self, parent, main, *args, **kwargs):
        super(Handle, self).__init__(parent, main, *args, **kwargs)

    def drawText(self, event, qp):
        qp.setPen(self.textColor())
        qp.setFont(QtGui.QFont('Arial', 10))
        qp.drawText(event.rect(), QtCore.Qt.AlignmentFlag.AlignLeft,
                    str(self.main.start()))
        qp.drawText(event.rect(), QtCore.Qt.AlignmentFlag.AlignRight,
                    str(self.main.end()))


class QRangeSlider(QtWidgets.QWidget, Ui_Form):
    minValueChanged = QtCore.pyqtSignal(int)
    maxValueChanged = QtCore.pyqtSignal(int)
    startValueChanged = QtCore.pyqtSignal(int)
    endValueChanged = QtCore.pyqtSignal(int)
    rangeChanged = QtCore.pyqtSignal(int, int)

    _INT_NUM = 2000
    _SPLIT_START = 1
    _SPLIT_END = 2

    def __init__(self, parent=None, *args, **kwargs):
        super(QRangeSlider, self).__init__(parent, *args, **kwargs)
        self.setupUi(self)
        self.setFixedHeight(21)
        self.setMouseTracking(False)
        self._splitter.splitterMoved.connect(self._handleMoveSplitter)
        self._head_layout = QtWidgets.QHBoxLayout()
        self._head_layout.setSpacing(0)
        self._head_layout.setContentsMargins(0, 0, 0, 0)
        self._head.setLayout(self._head_layout)
        self.head = Head(self._head, main=self)
        self._head_layout.addWidget(self.head)
        self._handle_layout = QtWidgets.QHBoxLayout()
        self._handle_layout.setSpacing(0)
        self._handle_layout.setContentsMargins(0, 0, 0, 0)
        self._handle.setLayout(self._handle_layout)
        self.handle = Handle(self._handle, main=self)
        self._handle_layout.addWidget(self.handle)
        self._tail_layout = QtWidgets.QHBoxLayout()
        self._tail_layout.setSpacing(0)
        self._tail_layout.setContentsMargins(0, 0, 0, 0)
        self._tail.setLayout(self._tail_layout)
        self.tail = Tail(self._tail, main=self)
        self._tail_layout.addWidget(self.tail)
        # set limits
        self.setMin(0)
        self.setMax(self._INT_NUM)
        self.setStart(0)
        self.setEnd(self._INT_NUM)
        self.setDrawValues(False)

    @QtCore.pyqtSlot(object)
    def resizeEvent(self, event):
        # The geometry changed and `self.width` is different now. Adjust
        # the entire range slider to reflect the new values.
        self.setStart(self.start())
        self.setEnd(self.end())
        super(QRangeSlider, self).resizeEvent(event)

    def min(self):
        return getattr(self, '__min', None)

    def max(self):
        return getattr(self, '__max', None)

    def setMin(self, value):
        setattr(self, '__min', value)
        self.minValueChanged.emit(value)

    def setMax(self, value):
        setattr(self, '__max', value)
        self.maxValueChanged.emit(value)

    def start(self):
        return getattr(self, '__start', None)

    def end(self):
        return getattr(self, '__end', None)

    def _setStart(self, value):
        setattr(self, '__start', value)
        self.startValueChanged.emit(value)
        self.rangeChanged.emit(value, self.end())

    def setStart(self, value):
        v = self._valueToPos(value)
        self._splitter.splitterMoved.disconnect()
        self._splitter.moveSplitter(v, self._SPLIT_START)
        self._splitter.refresh()
        self._splitter.splitterMoved.connect(self._handleMoveSplitter)
        self._setStart(value)

    def _setEnd(self, value):
        setattr(self, '__end', value)
        self.endValueChanged.emit(value)
        self.rangeChanged.emit(self.start(), value)

    def setEnd(self, value):
        v = self._valueToPos(value)
        self._splitter.splitterMoved.disconnect()
        self._splitter.moveSplitter(v, self._SPLIT_END)
        self._splitter.refresh()
        self._splitter.splitterMoved.connect(self._handleMoveSplitter)
        self._setEnd(value)

    def drawValues(self):
        return getattr(self, '__drawValues', None)

    def setDrawValues(self, draw):
        setattr(self, '__drawValues', draw)

    def getRange(self):
        return self.start(), self.end()

    def setRange(self, start, end):
        self.setStart(start)
        self.setEnd(end)

    def setBackgroundStyle(self, style):
        self._tail.setStyleSheet(style)
        self._head.setStyleSheet(style)

    def setSpanStyle(self, style):
        self._handle.setStyleSheet(style)

    def _valueToPos(self, value):
        return scale(value, (self.min(), self.max()), (0, self.width()))

    def _posToValue(self, xpos):
        return scale(xpos, (0, self.width()), (self.min(), self.max()))

    def _handleMoveSplitter(self, xpos, index):
        hw = self._splitter.handleWidth()
        if index == self._SPLIT_START:
            v = self._posToValue(xpos)
            if v >= self.end():
                self.setEnd(self._INT_NUM)
            self._setStart(v)
        elif index == self._SPLIT_END:
            v = self._posToValue(xpos + hw)
            if v <= self.start():
                self.setStart(0)
            self._setEnd(v)
