"""Screenshots for quick guide dcor"""
import sys
import time

from PyQt6 import QtCore
from PyQt6.QtWidgets import QApplication
from shapeout2.gui.main import ShapeOut2
from shapeout2.gui import dcor

app = QApplication(sys.argv)

QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.C))

mw = ShapeOut2()
mw.settings.setValue("check for updates", 0)
mw.settings.setValue("advanced/user confirm clear", 0)
mw.settings.remove("dcor/api key")

# show the dialog
dlg = dcor.DCORLoader(mw)
dlg.lineEdit_search.setText("sorting")
dlg.on_search()
# Now the dialog searches in another thread. Wait a little
# and only then take a screenshot.
for _ in range(5):
    time.sleep(.5)
    if dlg.listWidget.count() < 5:
        continue
# force redraw of scrollbars
dlg.listWidget.scrollToBottom()
dlg.listWidget.scrollToTop()
app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
dlg.grab().save("_qg_dcor_dlg.png")

mw.close()
