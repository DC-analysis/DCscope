"""Screenshots for quick guide R-lme4"""
import pathlib
import sys

from PyQt6 import QtCore
from PyQt6.QtWidgets import QApplication
from shapeout2.gui.main import ShapeOut2
from shapeout2.gui import compute

test_data = pathlib.Path(__file__).parent / ".." / ".." / "tests" / "data"


app = QApplication(sys.argv)

QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.C))

mw = ShapeOut2()
mw.settings.setValue("check for updates", 0)
mw.settings.setValue("advanced/user confirm clear", 0)

# build up a session
mw.on_action_open(test_data / "version_2_5_0_dcor_lme4.so2")

# create dialog manually
dlg = compute.ComputeSignificance(mw, pipeline=mw.pipeline)

# set the variables
# treatment rep 1
dlg.datasets[0].comboBox_group.setCurrentIndex(1)
# treatment rep 2
dlg.datasets[1].comboBox_group.setCurrentIndex(1)
dlg.datasets[1].spinBox_repeat.setValue(2)
# control rep 1
pass
# control rep 2
dlg.datasets[3].spinBox_repeat.setValue(2)
# control rep 3
dlg.datasets[4].spinBox_repeat.setValue(3)

# set the feature
feat_id = dlg.comboBox_feat.findData("deform")
dlg.comboBox_feat.setCurrentIndex(feat_id)

dlg.show()
QApplication.processEvents()
dlg.grab().save("_qg_lme4_init.png")

dlgr = dlg.on_lme4(ret_dlg=True)
dlgr.show()
QApplication.processEvents()
dlgr.grab().save("_qg_lme4_results.png")

mw.close()
