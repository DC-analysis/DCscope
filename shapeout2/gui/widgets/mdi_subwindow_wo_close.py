from PyQt6 import QtCore, QtWidgets


class MDISubWindowWOButtons(QtWidgets.QMdiSubWindow):
    def __init__(self, *args, **kwargs):
        super(MDISubWindowWOButtons, self).__init__(*args, **kwargs)
        self.setSystemMenu(None)
        self.setWindowFlags(QtCore.Qt.WindowType.CustomizeWindowHint
                            | QtCore.Qt.WindowType.WindowTitleHint)

    def closeEvent(self, event):
        event.ignore()
