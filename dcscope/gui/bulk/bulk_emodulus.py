import dclab
from dclab.features.emodulus.viscosity import (
    KNOWN_MEDIA, SAME_MEDIA, get_viscosity
)
import numpy as np

from PyQt6 import QtCore, QtWidgets

from .. import defaults
from ..analysis.ana_slot import SlotPanel
from ..widgets import show_wait_cursor

from .bulk_emodulus_ui import Ui_Dialog


class BulkActionEmodulus(QtWidgets.QDialog):
    #: Emitted when the pipeline is to be changed
    pp_mod_send = QtCore.pyqtSignal(dict)

    def __init__(self, parent, pipeline, *args, **kwargs):
        super(BulkActionEmodulus, self).__init__(parent=parent,
                                                 *args, **kwargs)

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        # main
        self.parent = self.parent

        # set pipeline
        self.pipeline = pipeline

        # ui choices
        self.ui.comboBox_medium.clear()
        self.ui.comboBox_medium.addItem("Other", "other")
        for name in SAME_MEDIA:
            self.ui.comboBox_medium.addItem(
                defaults.get_emodulus_medium_name(name), name)

        self.ui.comboBox_medium.addItem("Not defined", "undefined")
        self.ui.comboBox_medium.addItem("Unchanged", "unchanged")
        self.ui.comboBox_medium.setCurrentIndex(
            self.ui.comboBox_medium.findData("unchanged"))
        self.ui.comboBox_medium.currentIndexChanged.connect(self.on_cb_medium)

        self.ui.comboBox_temp.clear()
        self.ui.comboBox_temp.addItem("From feature", "feature")
        self.ui.comboBox_temp.addItem("From metadata", "config")
        self.ui.comboBox_temp.addItem("Manual", "manual")
        self.ui.comboBox_temp.setCurrentIndex(
            self.ui.comboBox_temp.findData("feature"))
        self.ui.comboBox_temp.currentIndexChanged.connect(self.on_cb_temp)

        # user-defined defaults (#129)
        emod_defaults = defaults.get_emodulus_defaults(QtCore.QSettings())

        self.ui.comboBox_visc_model.clear()
        for name, data in defaults.EMODULUS_VISC_MODELS.items():
            self.ui.comboBox_visc_model.addItem(name, data)
        self.ui.comboBox_visc_model.setCurrentIndex(
            self.ui.comboBox_visc_model.findData(
                emod_defaults["emodulus viscosity model"]))
        self.ui.comboBox_visc_model.currentIndexChanged.connect(
            self.on_cb_medium)

        self.ui.comboBox_lut.clear()
        lut_dict = dclab.features.emodulus.load.get_internal_lut_names_dict()
        for lut_id in lut_dict.keys():
            self.ui.comboBox_lut.addItem(lut_id, lut_id)
        # Set default LUT
        idx = self.ui.comboBox_lut.findData(emod_defaults["emodulus lut"])
        self.ui.comboBox_lut.setCurrentIndex(idx)

        # buttons
        btn_ok = self.ui.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok)
        btn_ok.clicked.connect(self.on_ok)

        # spin control
        self.ui.doubleSpinBox_temp.valueChanged.connect(self.on_cb_temp)

        self.on_cb_medium()

    @QtCore.pyqtSlot()
    def on_ok(self):
        with self.pipeline.lock:
            skipped = self.set_emodulus_properties()
        self.pp_mod_send.emit({"pipeline": {"feature_changed": "emodulus"}})
        if skipped:
            # Tell the user that the medium of some datasets was not
            # changed (#124).
            names = "\n".join(
                f"- {name}: {medium}" for name, medium in skipped)
            QtWidgets.QMessageBox.warning(
                self,
                "Medium not changed for some datasets",
                "The medium could not be changed for the following "
                "datasets, because a known medium is defined in the "
                "metadata of the measurement:\n\n"
                f"{names}\n\n"
                "For these datasets, the Young's modulus is computed "
                "with the medium (and viscosity) from the metadata.")

    @QtCore.pyqtSlot()
    def on_cb_medium(self):
        """User changed medium"""
        medium = self.ui.comboBox_medium.currentData()
        if medium in list(SAME_MEDIA.keys()) + ["unchanged"]:
            self.ui.doubleSpinBox_visc.setEnabled(False)
            self.ui.comboBox_temp.setEnabled(True)
            self.ui.comboBox_visc_model.setEnabled(True)
        else:
            self.ui.doubleSpinBox_visc.setEnabled(True)
            self.ui.comboBox_temp.setEnabled(False)
            self.ui.comboBox_visc_model.setEnabled(False)
        self.on_cb_temp()

    @QtCore.pyqtSlot()
    def on_cb_temp(self):
        """User changed temperature"""
        temp = self.ui.comboBox_temp.currentData()

        if (not self.ui.comboBox_temp.isEnabled()
                or temp in ["feature", "config"]):
            self.ui.doubleSpinBox_temp.setEnabled(False)
            self.ui.doubleSpinBox_temp.setValue(np.nan)
        else:
            self.ui.doubleSpinBox_temp.setEnabled(True)
            if np.isnan(self.ui.doubleSpinBox_temp.value()):
                self.ui.doubleSpinBox_temp.setValue(23)

        self.update_viscosity()

    @show_wait_cursor
    @QtCore.pyqtSlot()
    def set_emodulus_properties(self):
        """Set the given emodulus properties for all datasets

        Returns
        -------
        skipped: list of tuple
            Names and media of the datasets for which the medium
            could not be set, because a known medium is defined in
            the metadata of the dataset
        """
        medium = self.ui.comboBox_medium.currentData()
        visc_model = self.ui.comboBox_visc_model.currentData()
        lut = self.ui.comboBox_lut.currentData()
        if self.ui.comboBox_temp.isEnabled():
            scen = self.ui.comboBox_temp.currentData()
        else:
            scen = None
        if self.ui.doubleSpinBox_temp.isEnabled():
            tempval = self.ui.doubleSpinBox_temp.value()
        else:
            tempval = None
        if self.ui.doubleSpinBox_visc.isEnabled():
            viscval = self.ui.doubleSpinBox_visc.value()
        else:
            viscval = None

        skipped = []

        if len(self.pipeline.slots) == 0:
            return skipped

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
            elif medium != "unchanged":
                # The medium is defined in the metadata (#124)
                skipped.append((slot.name, valid_media[0][0]))

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

        return skipped

    def update_viscosity(self):
        """Update viscosity shown"""
        temp = self.ui.comboBox_temp.currentData()

        if (not self.ui.comboBox_temp.isEnabled()
                or temp in ["feature", "config"]):
            self.ui.doubleSpinBox_visc.setValue(np.nan)
            self.ui.doubleSpinBox_visc.setToolTip("unique values per dataset")
        else:
            # update the viscosity value shown in the spin control
            medium = self.ui.comboBox_medium.currentData()
            if medium in KNOWN_MEDIA:
                visc = get_viscosity(
                    temperature=self.ui.doubleSpinBox_temp.value(),
                    medium=medium,
                    model=self.ui.comboBox_visc_model.currentData(),
                )
                tooltip = "valid for 0.16 µL/s flow rate and 20 µm channel"
            else:
                visc = np.nan
                tooltip = ""
            self.ui.doubleSpinBox_visc.setValue(visc)
            self.ui.doubleSpinBox_visc.setToolTip(tooltip)
