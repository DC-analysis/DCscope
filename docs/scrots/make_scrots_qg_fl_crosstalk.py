"""Screenshots for quick guide fluorescence crosstalk"""
import os
import sys
import tempfile

import dclab
import numpy as np
from PyQt6 import QtCore
from PyQt6.QtWidgets import QApplication
from dcscope.gui.main import DCscope

import scrots_common

app = QApplication(sys.argv)
scrots_common.setup_icon_theme()

QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.Language.C))

mw = DCscope()
mw.settings.setValue("check for updates", 0)
mw.settings.setValue("advanced/user confirm clear", 0)

# create a fake dataset with three fluorescence channels
rng = np.random.default_rng(42)
size = 1000
tmp = tempfile.mktemp(".rtdc", prefix="example_")
with dclab.RTDCWriter(tmp, mode="reset") as hw:
    hw.store_metadata({"experiment": {"sample": "crosstalk example",
                                      "date": "2026-11-17",
                                      "event count": size,
                                      "run index": 1,
                                      "time": "12:00:00"},
                       "imaging": {"pixel size": 0.34,
                                   "frame rate": 2000},
                       "setup": {"channel width": 20,
                                 "chip region": "channel",
                                 "flow rate": 0.06,
                                 "medium": "CellCarrier"},
                       "fluorescence": {"channel 1 name": "FITC",
                                        "channel 2 name": "PE",
                                        "channel 3 name": "APC",
                                        "channel count": 3,
                                        "channels installed": 3,
                                        "laser count": 2,
                                        "lasers installed": 3,
                                        "sample rate": 1000000,
                                        "samples per event": 100,
                                        "signal max": 1,
                                        "signal min": -1,
                                        },
                       })
    hw.store_feature("deform", rng.uniform(0.01, 0.1, size))
    hw.store_feature("area_um", rng.uniform(20, 80, size))
    hw.store_feature("fl1_max", rng.uniform(10, 1000, size))
    hw.store_feature("fl2_max", rng.uniform(10, 1000, size))
    hw.store_feature("fl3_max", rng.uniform(10, 1000, size))

# build up a session
mw.add_dataslot(paths=[tmp])

# analysis view
mw.on_modify_slot(mw.pipeline.slot_ids[0])
mw.widget_ana_view.repaint()
wsl = mw.widget_ana_view.ui.widget_slot
wsl.ui.groupBox_fl_cross.setFixedSize(360, 150)

wsl.ui.doubleSpinBox_ct12.setValue(0.214)
wsl.ui.doubleSpinBox_ct13.setValue(0.012)
wsl.ui.doubleSpinBox_ct21.setValue(0.031)
wsl.ui.doubleSpinBox_ct23.setValue(0.086)
wsl.ui.doubleSpinBox_ct31.setValue(0.0)
wsl.ui.doubleSpinBox_ct32.setValue(0.004)
app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
wsl.ui.groupBox_fl_cross.grab().save("_qg_fl_crosstalk_matrix.png")

mw.close()

os.remove(tmp)
