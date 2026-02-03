import importlib.resources

import dclab
from dclab.features.emodulus.viscosity import (
    KNOWN_MEDIA, SAME_MEDIA, get_viscosity
)
import numpy as np

from PyQt6 import uic, QtCore, QtWidgets

from dcscope.gui.analysis.ana_slot import SlotPanel
from dcscope.gui.widgets import show_wait_cursor


class BulkActionEmodulus(QtWidgets.QDialog):
    #: Emitted when the pipeline is to be changed
    pp_mod_send = QtCore.pyqtSignal(dict)

    def __init__(self, parent, pipeline, *args, **kwargs):
        super(BulkActionEmodulus, self).__init__(parent=parent,
                                                 *args, **kwargs)
        ref = importlib.resources.files(
            "dcscope.gui.bulk") / "bulk_emodulus.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        # main
        self.parent = self.parent

        # set pipeline
        self.pipeline = pipeline

        # ui choices
        self.comboBox_medium.clear()
        self.comboBox_medium.addItem("Other", "other")
        for name in SAME_MEDIA:
            for sk in SAME_MEDIA[name]:
                if sk.count("Cell"):  # just add CellCarrier information
                    info = f" ({sk})"
                    break
            else:
                info = ""
            self.comboBox_medium.addItem(name + info, name)

        self.comboBox_medium.addItem("Not defined", "undefined")
        self.comboBox_medium.addItem("Unchanged", "unchanged")
        self.comboBox_medium.setCurrentIndex(
            self.comboBox_medium.findData("unchanged"))
        self.comboBox_medium.currentIndexChanged.connect(self.on_cb_medium)

        self.comboBox_temp.clear()
        self.comboBox_temp.addItem("From feature", "feature")
        self.comboBox_temp.addItem("From meta data", "config")
        self.comboBox_temp.addItem("Manual", "manual")
        self.comboBox_temp.setCurrentIndex(
            self.comboBox_temp.findData("feature"))
        self.comboBox_temp.currentIndexChanged.connect(self.on_cb_temp)

        self.comboBox_visc_model.clear()
        self.comboBox_visc_model.addItem("buyukurganci-2022",
                                         "buyukurganci-2022")
        self.comboBox_visc_model.addItem("herold-2017", "herold-2017")
        self.comboBox_visc_model.setCurrentIndex(
            self.comboBox_visc_model.findData("buyukurganci-2022"))
        self.comboBox_visc_model.currentIndexChanged.connect(self.on_cb_medium)

        self.comboBox_lut.clear()
        lut_dict = dclab.features.emodulus.load.get_internal_lut_names_dict()
        for lut_id in lut_dict.keys():
            self.comboBox_lut.addItem(lut_id, lut_id)
        # Set default LUT
        idx = self.comboBox_lut.findData("LE-2D-FEM-19")
        self.comboBox_lut.setCurrentIndex(idx)

        # buttons
        btn_ok = self.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok)
        btn_ok.clicked.connect(self.on_ok)

        # spin control
        self.doubleSpinBox_temp.valueChanged.connect(self.on_cb_temp)

        self.on_cb_medium()

    @QtCore.pyqtSlot()
    def on_ok(self):
        with self.pipeline.lock:
            self.set_emodulus_properties()
            self.pp_mod_send.emit(
                {"pipeline": {"feature_changed": "emodulus"}})

    @QtCore.pyqtSlot()
    def on_cb_medium(self):
        """User changed medium"""
        medium = self.comboBox_medium.currentData()
        if medium in list(SAME_MEDIA.keys()) + ["unchanged"]:
            self.doubleSpinBox_visc.setEnabled(False)
            self.comboBox_temp.setEnabled(True)
            self.comboBox_visc_model.setEnabled(True)
        else:
            self.doubleSpinBox_visc.setEnabled(True)
            self.comboBox_temp.setEnabled(False)
            self.comboBox_visc_model.setEnabled(False)
        self.on_cb_temp()

    @QtCore.pyqtSlot()
    def on_cb_temp(self):
        """User changed temperature"""
        temp = self.comboBox_temp.currentData()

        if not self.comboBox_temp.isEnabled() or temp in ["feature", "config"]:
            self.doubleSpinBox_temp.setEnabled(False)
            self.doubleSpinBox_temp.setValue(np.nan)
        else:
            self.doubleSpinBox_temp.setEnabled(True)
            if np.isnan(self.doubleSpinBox_temp.value()):
                self.doubleSpinBox_temp.setValue(23)

        self.update_viscosity()

    @show_wait_cursor
    @QtCore.pyqtSlot()
    def set_emodulus_properties(self):
        """Set the given emodulus properties for all datasets"""
        medium = self.comboBox_medium.currentData()
        visc_model = self.comboBox_visc_model.currentData()
        lut = self.comboBox_lut.currentData()
        if self.comboBox_temp.isEnabled():
            scen = self.comboBox_temp.currentData()
        else:
            scen = None
        if self.doubleSpinBox_temp.isEnabled():
            tempval = self.doubleSpinBox_temp.value()
        else:
            tempval = None
        if self.doubleSpinBox_visc.isEnabled():
            viscval = self.doubleSpinBox_visc.value()
        else:
            viscval = None

        if len(self.pipeline.slots) == 0:
            return

        for slot in self.pipeline.slots:
            ds = slot.get_dataset()

            # Use the internal sanity checks to determine whether
            # we can set the medium or temperature scenarios.
            valid_media = SlotPanel.get_dataset_choices_medium(ds)
            valid_scenarios = SlotPanel.get_dataset_choices_temperature(ds)

            state = slot.__getstate__()

            if medium in [m[1] for m in valid_media]:
                state["emodulus"]["emodulus medium"] = medium
                # Set the viscosity here, because unknown media are
                # available.
                if viscval is not None:
                    state["emodulus"]["emodulus viscosity"] = viscval

            if scen in [s[1] for s in valid_scenarios]:  # scen is not None
                state["emodulus"]["emodulus scenario"] = scen
                if tempval is not None:
                    state["emodulus"]["emodulus temperature"] = tempval

            if state["emodulus"]["emodulus medium"] in KNOWN_MEDIA:
                state["emodulus"]["emodulus viscosity model"] = visc_model
            else:
                if "emodulus viscosity model" in state["emodulus"]:
                    state["emodulus"].pop("emodulus viscosity model")

            state["emodulus"]["emodulus lut"] = lut

            slot.__setstate__(state)

    def update_viscosity(self):
        """Update viscosity shown"""
        temp = self.comboBox_temp.currentData()

        if not self.comboBox_temp.isEnabled() or temp in ["feature", "config"]:
            self.doubleSpinBox_visc.setValue(np.nan)
            self.doubleSpinBox_visc.setToolTip("unique values per dataset")
        else:
            # update the viscosity value shown in the spin control
            medium = self.comboBox_medium.currentData()
            if medium in KNOWN_MEDIA:
                visc = get_viscosity(
                    temperature=self.doubleSpinBox_temp.value(),
                    medium=medium,
                    model=self.comboBox_visc_model.currentData(),
                )
                tooltip = "valid for 0.16 µL/s flow rate and 20 µm channel"
            else:
                visc = np.nan
                tooltip = ""
            self.doubleSpinBox_visc.setValue(visc)
            self.doubleSpinBox_visc.setToolTip(tooltip)
