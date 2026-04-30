"""Screenshots for quick guide dcor"""
import sys

from PyQt6 import QtCore, QtTest
from PyQt6.QtWidgets import QApplication
from dcscope.gui.main import DCscope
from dcscope.gui import dcor

app = QApplication(sys.argv)

QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.Language.C))

mw = DCscope()
mw.settings.setValue("check for updates", 0)
mw.settings.setValue("advanced/user confirm clear", 0)
mw.settings.remove("dcor/api key")
mw.settings.setValue("dcor/servers", ["dcor.mpl.mpg.de"])

# show the dialog
dlg = dcor.DCORLoader(mw)
dlg.show()
dlg.ui.lineEdit_search.setText("sorting")
dlg.on_search()
# Now the dialog searches in another thread. Wait a little
# and only then take a screenshot.
for _ in range(10):
    QtTest.QTest.qWait(500)
    if dlg.ui.listWidget.count() > 10:
        break
else:
    print("No search results")
# force redraw of scrollbars
dlg.ui.listWidget.scrollToBottom()
dlg.ui.listWidget.scrollToTop()
app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
dlg.grab().save("_qg_dcor_dlg.png")
dlg.close()

mw.close()
