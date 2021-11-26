"""Screenshots for quick guide extensions"""
import pathlib
import sys

from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication
from shapeout2.gui.main import ShapeOut2
from shapeout2.gui import preferences

data_path = pathlib.Path(__file__).resolve().parent / ".." / "data"

app = QApplication(sys.argv)

QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.C))

mw = ShapeOut2()
mw.settings.setValue("check for updates", 0)
mw.settings.setValue("advanced/check pyqtgraph version", 0)

try:
    mw.extensions.import_extension_from_path(
        data_path / "naive_rbc_score.modc")
except BaseException:
    # Probably already loaded
    pass

try:
    mw.extensions.import_extension_from_path(
        data_path / "estension_fl1_density.py")
except BaseException:
    # Probably already loaded
    pass


# open the dialog window
dlg = preferences.Preferences(mw)
dlg.tabWidget.setCurrentIndex(3)

dlg.show()
QApplication.processEvents(QtCore.QEventLoop.AllEvents, 300)
dlg.grab().save("_qg_extensions.png")

mw.close()
