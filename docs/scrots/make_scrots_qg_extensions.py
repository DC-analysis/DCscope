"""Screenshots for quick guide extensions"""
import pathlib
import sys

from PyQt6 import QtCore
from PyQt6.QtWidgets import QApplication
from dcscope.gui.main import DCscope
from dcscope.gui import preferences

import scrots_common

data_path = pathlib.Path(__file__).resolve().parent / ".." / "data"

app = QApplication(sys.argv)
scrots_common.setup_icon_theme()
scrots_common.setup_style()
scrots_common.use_default_settings()

QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.Language.C))

mw = DCscope()
mw.settings.setValue("check for updates", 0)
mw.settings.setValue("advanced/user confirm clear", 0)

mw.extensions.import_extension_from_path(
    data_path / "extension_fl1_density.py")

# open the dialog window
dlg = preferences.Preferences(mw)
dlg.ui.tabWidget.setCurrentIndex(4)

dlg.show()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
dlg.grab().save("_qg_extensions.png")

mw.close()
