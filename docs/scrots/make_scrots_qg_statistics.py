"""Screenshots for quick guide statistics"""
import sys

from PyQt6 import QtCore
from PyQt6.QtWidgets import QApplication
from shapeout2.gui.main import ShapeOut2
from shapeout2.gui import compute

app = QApplication(sys.argv)

QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.C))

mw = ShapeOut2()
mw.settings.setValue("check for updates", 0)
mw.settings.setValue("advanced/user confirm clear", 0)

# build up a session
mw.add_dataslot(paths=["Figure3_Blood_Initial.rtdc"])
mw.reload_pipeline()


# open the dialog window
dlg = compute.ComputeStatistics(mw, pipeline=mw.pipeline)
dlg.bulklist_features.listWidget.item(1).setCheckState(2)
dlg.show()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
dlg.grab().save("_qg_statistics_init.png")

dlg.path = "/some/other/path/to/data"
dlg.lineEdit_path.setText(dlg.path)
dlg.comboBox.setCurrentIndex(1)
dlg.comboBox_filter_ray.setCurrentIndex(1)
dlg.bulklist_features.listWidget.item(4).setCheckState(2)
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
dlg.grab().save("_qg_statistics_folder.png")

mw.close()
