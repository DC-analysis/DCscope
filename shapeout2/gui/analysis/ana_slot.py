import copy
import importlib.resources
import warnings

import dclab
from dclab.features.emodulus.viscosity import (
    ALIAS_MEDIA, KNOWN_MEDIA, TemperatureOutOfRangeWarning
)
import numpy as np
from PyQt6 import uic, QtCore, QtWidgets

from ... import meta_tool
from ...pipeline import Dataslot

from .dlg_slot_reorder import DlgSlotReorder


class SlotPanel(QtWidgets.QWidget):
    #: Emitted when a shapeout2.pipeline.Dataslot is to be changed
    slot_changed = QtCore.pyqtSignal(dict)
    #: Emitted when the pipeline is to be changed
    pipeline_changed = QtCore.pyqtSignal(dict)

    def __init__(self, *args, **kwargs):
        super(SlotPanel, self).__init__(*args, **kwargs)
        ref = importlib.resources.files(
            "shapeout2.gui.analysis") / "ana_slot.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        # current Shape-Out 2 pipeline
        self._pipeline = None
        # signals
        self.toolButton_reorder.clicked.connect(self.on_reorder_slots)
        self.toolButton_anew.clicked.connect(self.on_anew_slot)
        self.toolButton_duplicate.clicked.connect(self.on_duplicate_slot)
        self.toolButton_remove.clicked.connect(self.on_remove_slot)
        self.pushButton_apply.clicked.connect(self.write_slot)
        self.pushButton_reset.clicked.connect(self.update_content)
        self.comboBox_slots.currentIndexChanged.connect(self.update_content)
        self.comboBox_medium.currentIndexChanged.connect(self.on_ui_changed)
        self.comboBox_temp.currentIndexChanged.connect(self.on_ui_changed)
        self.comboBox_visc_model.currentIndexChanged.connect(
            self.on_ui_changed)
        self.doubleSpinBox_temp.valueChanged.connect(self.on_ui_changed)
        # init
        self._update_emodulus_medium_choices()
        self._update_emodulus_temp_choices()
        self._update_emodulus_lut_choices()
        self._update_emodulus_visc_model_choices()

        self.update_content()

    def __getstate__(self):
        slot_state = self.current_slot_state
        if self.comboBox_temp.currentData() in ["manual", "config"]:
            emod_temp = self.doubleSpinBox_temp.value()
        else:
            emod_temp = np.nan
        if self.comboBox_medium.currentData() in KNOWN_MEDIA:
            emod_visc = np.nan  # viscosity computed for known medium
            scenario = self.comboBox_temp.currentData()
        elif self.comboBox_medium.currentData() == "unknown":
            emod_visc = np.nan  # viscosity not defined
            scenario = None
        else:  # "other", user-defined medium
            emod_visc = self.doubleSpinBox_visc.value()  # user input
            scenario = None
        emod_visc_model = self.comboBox_visc_model.currentData()
        emod_select_lut = self.comboBox_lut.currentText()
        state = {
            "identifier": slot_state["identifier"],
            "name": self.lineEdit_name.text(),
            "path": slot_state["path"],
            "color": self.pushButton_color.color().name(),
            "slot used": self.checkBox_use.isChecked(),
            "fl names": {"FL-1": self.lineEdit_fl1.text(),
                         "FL-2": self.lineEdit_fl2.text(),
                         "FL-3": self.lineEdit_fl3.text(),
                         },
            "crosstalk": {
                "crosstalk fl12": self.doubleSpinBox_ct12.value(),
                "crosstalk fl13": self.doubleSpinBox_ct13.value(),
                "crosstalk fl21": self.doubleSpinBox_ct21.value(),
                "crosstalk fl23": self.doubleSpinBox_ct23.value(),
                "crosstalk fl31": self.doubleSpinBox_ct31.value(),
                "crosstalk fl32": self.doubleSpinBox_ct32.value(),
            },
            "emodulus": {
                "emodulus enabled": slot_state["emodulus"]["emodulus enabled"],
                "emodulus lut": emod_select_lut,
                # It is ok if we have user-defined strings here, because
                # only media in KNOWN_MEDIA are passed to dclab in the end.
                "emodulus medium": self.comboBox_medium.currentData(),
                "emodulus scenario": scenario,
                "emodulus temperature": emod_temp,
                "emodulus viscosity": emod_visc,
                "emodulus viscosity model": emod_visc_model,
            }
        }
        return state

    def __setstate__(self, state):
        cur_state = self.current_slot_state
        if cur_state["identifier"] != state["identifier"]:
            raise ValueError("Slot identifier mismatch!")
        self.lineEdit_name.setText(state["name"])
        self.lineEdit_path.setText(str(state["path"]))
        self.pushButton_color.setColor(state["color"])
        self.lineEdit_fl1.setText(state["fl names"]["FL-1"])
        self.lineEdit_fl2.setText(state["fl names"]["FL-2"])
        self.lineEdit_fl3.setText(state["fl names"]["FL-3"])
        self.checkBox_use.setChecked(state["slot used"])
        # crosstalk
        crosstalk = state["crosstalk"]
        self.doubleSpinBox_ct12.setValue(crosstalk["crosstalk fl12"])
        self.doubleSpinBox_ct13.setValue(crosstalk["crosstalk fl13"])
        self.doubleSpinBox_ct21.setValue(crosstalk["crosstalk fl21"])
        self.doubleSpinBox_ct23.setValue(crosstalk["crosstalk fl23"])
        self.doubleSpinBox_ct31.setValue(crosstalk["crosstalk fl31"])
        self.doubleSpinBox_ct32.setValue(crosstalk["crosstalk fl32"])
        # emodulus
        # updating the medium/temperature choices has to be done first,
        # because self.comboBox_medium triggers the function on_ui_changed.
        self._update_emodulus_medium_choices()
        self._update_emodulus_temp_choices()
        emodulus = state["emodulus"]
        self.groupBox_emod.setVisible(emodulus["emodulus enabled"])
        idx_med = self.comboBox_medium.findData(emodulus["emodulus medium"])
        if idx_med == -1:  # empty medium string
            idx_med = self.comboBox_medium.findData("other")
        self.comboBox_medium.setCurrentIndex(idx_med)
        cfg = meta_tool.get_rtdc_config(state["path"])
        if "medium" in cfg["setup"] and cfg["setup"]["medium"] in KNOWN_MEDIA:
            self.comboBox_medium.setEnabled(False)  # prevent modification
        else:
            self.comboBox_medium.setEnabled(True)  # user-defined
        # https://dclab.readthedocs.io/en/latest/sec_av_emodulus.html
        scenario = emodulus.get("emodulus scenario", "manual")
        if scenario:
            idx_scen = self.comboBox_temp.findData(scenario)
            self.comboBox_temp.blockSignals(True)
            self.comboBox_temp.setCurrentIndex(idx_scen)
            self.comboBox_temp.blockSignals(False)

        idx_vm = self.comboBox_visc_model.findData(
            # use defaults from previous session (Herold-2107)
            emodulus.get("emodulus viscosity model", "herold-2017"))

        self.comboBox_visc_model.setCurrentIndex(idx_vm)
        # Set current state of the emodulus lut
        idx_lut = self.comboBox_lut.findData(emodulus.get("emodulus lut", ""))
        self.comboBox_lut.setCurrentIndex(idx_lut)
        # This has to be done after setting the scenario
        # (otherwise it might be overridden in the frontend)
        self.doubleSpinBox_temp.setValue(emodulus["emodulus temperature"])
        self.doubleSpinBox_visc.setValue(emodulus["emodulus viscosity"])

        # Fluorescence data visibility
        features = meta_tool.get_rtdc_features(state["path"])
        hasfl1 = "fl1_max" in features
        hasfl2 = "fl2_max" in features
        hasfl3 = "fl3_max" in features

        # labels
        self.lineEdit_fl1.setVisible(hasfl1)
        self.label_fl1.setVisible(hasfl1)
        self.lineEdit_fl2.setVisible(hasfl2)
        self.label_fl2.setVisible(hasfl2)
        self.lineEdit_fl3.setVisible(hasfl3)
        self.label_fl3.setVisible(hasfl3)

        # crosstalk matrix
        self.label_from_fl1.setVisible(hasfl1 & hasfl2 | hasfl1 & hasfl3)
        self.label_from_fl2.setVisible(hasfl2 & hasfl1 | hasfl2 & hasfl3)
        self.label_from_fl3.setVisible(hasfl3 & hasfl1 | hasfl3 & hasfl2)
        self.label_to_fl1.setVisible(hasfl1 & hasfl2 | hasfl1 & hasfl3)
        self.label_to_fl2.setVisible(hasfl2 & hasfl1 | hasfl2 & hasfl3)
        self.label_to_fl3.setVisible(hasfl3 & hasfl1 | hasfl3 & hasfl2)
        self.doubleSpinBox_ct12.setVisible(hasfl1 & hasfl2)
        self.doubleSpinBox_ct13.setVisible(hasfl1 & hasfl3)
        self.doubleSpinBox_ct21.setVisible(hasfl2 & hasfl1)
        self.doubleSpinBox_ct23.setVisible(hasfl2 & hasfl3)
        self.doubleSpinBox_ct31.setVisible(hasfl3 & hasfl1)
        self.doubleSpinBox_ct32.setVisible(hasfl3 & hasfl2)

        self.groupBox_fl_labels.setVisible(hasfl1 | hasfl2 | hasfl3)
        self.groupBox_fl_cross.setVisible(hasfl1 | hasfl2 | hasfl3)

    @staticmethod
    def get_dataset_choices_medium(ds):
        """Return the choices for the medium selection

        Parameters
        ----------
        ds: RTDCBase
            Dataset

        Returns
        -------
        choices: list
            List of [title, identifier]
        """
        if ds:
            medium = ds.config.get("setup", {}).get("medium", "").strip()
            if not medium:  # empty medium string
                medium = "other"
        else:
            medium = "undefined"
        if medium in KNOWN_MEDIA:
            valid_media = [medium]
        else:
            valid_media = KNOWN_MEDIA + [medium, "other", "undefined"]
        choices = []
        for vm in valid_media:
            if vm == "CellCarrierB":
                name = "CellCarrier B"  # [sic]
            else:
                name = vm
            choices.append([name, vm])
        return choices

    @staticmethod
    def get_dataset_choices_temperature(ds):
        """Return the choices for the temperature selection

        Parameters
        ----------
        ds: RTDCBase
            Dataset

        Returns
        -------
        choices: list
            List of [title, identifier]
        """
        choices = []
        if ds is not None:
            if "temp" in ds:
                choices.append(["From feature", "feature"])
            if "temperature" in ds.config["setup"]:
                choices.append(["From meta data", "config"])
        choices.append(["Manual", "manual"])
        return choices

    def _update_emodulus_medium_choices(self):
        """update currently available medium choices for YM

        Signals are blocked.
        """
        self.comboBox_medium.blockSignals(True)
        self.comboBox_medium.clear()
        ds = self.get_dataset()
        choices = self.get_dataset_choices_medium(ds)
        for name, data in choices:
            self.comboBox_medium.addItem(name, data)
        self.comboBox_medium.blockSignals(False)

    def _update_emodulus_temp_choices(self):
        """pupdate temperature choices for YM

        The previous selection is preserved. Signals are blocked.
        """
        self.comboBox_temp.blockSignals(True)
        cursel = self.comboBox_temp.currentData()
        self.comboBox_temp.clear()
        ds = self.get_dataset()
        choices = self.get_dataset_choices_temperature(ds)
        for name, data in choices:
            self.comboBox_temp.addItem(name, data)
        idx = self.comboBox_temp.findData(cursel)
        self.comboBox_temp.setCurrentIndex(idx)
        self.comboBox_temp.blockSignals(False)

    def _update_emodulus_lut_choices(self):
        """update currently available LUT choices for YM

        The previous selection is preserved. Signals are blocked.
        """
        self.comboBox_lut.blockSignals(True)
        cursel = self.comboBox_lut.currentData()
        self.comboBox_lut.clear()
        lut_dict = dclab.features.emodulus.load.get_internal_lut_names_dict()
        for lut_id in lut_dict.keys():
            self.comboBox_lut.addItem(lut_id, lut_id)
        idx = self.comboBox_lut.findData(cursel)
        self.comboBox_lut.setCurrentIndex(idx)
        self.comboBox_lut.blockSignals(False)

    def _update_emodulus_visc_model_choices(self):
        """update currently available viscosity model choices for YM

        Signals are blocked.
        """
        self.comboBox_visc_model.blockSignals(True)
        self.comboBox_visc_model.clear()

        choices = {"Herold (2017)": "herold-2017",
                   "Buyukurganci (2022)": "buyukurganci-2022"}
        for name, data in choices.items():
            self.comboBox_visc_model.addItem(name, data)
        self.comboBox_visc_model.blockSignals(False)

    @property
    def current_slot_state(self):
        if self.slot_ids:
            slot_index = self.comboBox_slots.currentIndex()
            slot_state = self.pipeline.slots[slot_index].__getstate__()
        else:
            slot_state = None
        return slot_state

    @property
    def pipeline(self):
        return self._pipeline

    @property
    def slot_ids(self):
        """List of slot identifiers"""
        if self.pipeline is None:
            return []
        else:
            return [slot.identifier for slot in self.pipeline.slots]

    @property
    def slot_names(self):
        """List of slot names"""
        if self.pipeline is None:
            return []
        else:
            return [slot.name for slot in self.pipeline.slots]

    def get_dataset(self):
        """Return dataset associated with the current slot index

        Returns None if there is no dataset in the pipeline.
        """
        if self.pipeline is not None and self.pipeline.slots:
            slot_index = self.comboBox_slots.currentIndex()
            slot = self.pipeline.slots[slot_index]
            return slot.get_dataset()
        else:
            return None

    @QtCore.pyqtSlot()
    def on_anew_slot(self):
        slot_state = self.__getstate__()
        new_slot = Dataslot(slot_state["path"])
        pos = self.pipeline.slot_ids.index(slot_state["identifier"])
        self.pipeline.add_slot(new_slot, index=pos + 1)
        state = self.pipeline.__getstate__()
        self.pipeline_changed.emit(state)

    @QtCore.pyqtSlot()
    def on_duplicate_slot(self):
        # determine the new filter state
        slot_state = self.__getstate__()
        new_state = copy.deepcopy(slot_state)
        new_slot = Dataslot(slot_state["path"])
        new_state["identifier"] = new_slot.identifier
        new_state["name"] = new_slot.name
        new_slot.__setstate__(new_state)
        # determine the filter position
        pos = self.pipeline.slot_ids.index(slot_state["identifier"])
        self.pipeline.add_slot(new_slot, index=pos + 1)
        state = self.pipeline.__getstate__()
        self.pipeline_changed.emit(state)

    @QtCore.pyqtSlot()
    def on_remove_slot(self):
        slot_state = self.__getstate__()
        self.pipeline.remove_slot(slot_state["identifier"])
        state = self.pipeline.__getstate__()
        self.pipeline_changed.emit(state)

    @QtCore.pyqtSlot()
    def on_reorder_slots(self):
        """Open dialog for reordering slots"""
        dlg = DlgSlotReorder(self.pipeline, self)
        dlg.pipeline_changed.connect(self.pipeline_changed)
        dlg.exec()

    @QtCore.pyqtSlot()
    def on_ui_changed(self):
        """Called when the user modifies the medium or temperature options"""
        medium = self.comboBox_medium.currentData()
        tselec = self.comboBox_temp.currentData()
        medium_key = ALIAS_MEDIA.get(medium, medium)
        visc_model = self.comboBox_visc_model.currentData()
        # Only show model selection if we are dealing with MC-PBS
        self.comboBox_visc_model.setVisible(medium_key.count("MC-PBS"))
        self.doubleSpinBox_visc.setStyleSheet("")
        if medium in KNOWN_MEDIA:  # medium registered with dclab
            self.label_temp.setVisible(True)
            self.comboBox_temp.setVisible(True)
            self.doubleSpinBox_temp.setVisible(True)
            self.comboBox_temp.setEnabled(True)
            self.doubleSpinBox_visc.setEnabled(True)
            self.doubleSpinBox_visc.setReadOnly(True)
            if tselec == "manual":
                temperature = self.doubleSpinBox_temp.value()
                self.doubleSpinBox_temp.setEnabled(True)
                self.doubleSpinBox_temp.setReadOnly(False)
            elif tselec == "config":
                # get temperature from dataset
                ds = self.get_dataset()
                temperature = ds.config["setup"]["temperature"]
                self.doubleSpinBox_temp.setEnabled(True)
                self.doubleSpinBox_temp.setReadOnly(True)
                self.doubleSpinBox_temp.setValue(temperature)
            elif tselec == "feature":
                temperature = np.nan
                self.doubleSpinBox_temp.setEnabled(False)
                self.doubleSpinBox_temp.setVisible(False)
                self.doubleSpinBox_temp.setValue(temperature)
            else:
                assert tselec is None, "We should still be in init"
                return
            # For user convenience, also show the viscosity
            if medium in KNOWN_MEDIA and not np.isnan(temperature):
                # compute viscosity
                state = self.__getstate__()
                cfg = meta_tool.get_rtdc_config(state["path"])
                with warnings.catch_warnings(record=True) as w:
                    # Warn the user if the temperature is out-of-range
                    warnings.simplefilter("always")
                    visc = dclab.features.emodulus.viscosity.get_viscosity(
                        medium=medium,
                        channel_width=cfg["setup"]["channel width"],
                        flow_rate=cfg["setup"]["flow rate"],
                        temperature=temperature,
                        model=visc_model,
                    )
                    for wi in w:
                        if issubclass(wi.category,
                                      TemperatureOutOfRangeWarning):
                            vstyle = "color: #950000; border-width: 2px"
                            break
                    else:
                        vstyle = "border-width: 2px"
                self.doubleSpinBox_visc.setVisible(True)
                self.doubleSpinBox_visc.setEnabled(True)
                self.doubleSpinBox_visc.setReadOnly(True)
                self.doubleSpinBox_visc.setValue(visc)
                self.doubleSpinBox_visc.setStyleSheet(vstyle)
            else:
                self.doubleSpinBox_visc.setEnabled(False)
                self.doubleSpinBox_visc.setVisible(False)
                self.doubleSpinBox_visc.setReadOnly(True)
                self.doubleSpinBox_visc.setValue(np.nan)
        elif medium == "undefined":
            self.label_temp.setVisible(False)
            self.comboBox_temp.setVisible(False)
            self.doubleSpinBox_temp.setVisible(False)
            self.doubleSpinBox_temp.setEnabled(False)
            self.doubleSpinBox_temp.setValue(np.nan)
            self.doubleSpinBox_visc.setValue(np.nan)
            self.doubleSpinBox_visc.setEnabled(False)
        else:  # "other" or user-defined
            self.label_temp.setVisible(False)
            self.comboBox_temp.setVisible(False)
            self.doubleSpinBox_temp.setVisible(False)
            self.doubleSpinBox_temp.setEnabled(False)
            self.doubleSpinBox_temp.setValue(np.nan)
            self.doubleSpinBox_visc.setEnabled(True)
            self.doubleSpinBox_visc.setReadOnly(False)

    def set_pipeline(self, pipeline):
        self._pipeline = pipeline

    def show_slot(self, slot_id):
        self.update_content(slot_index=self.slot_ids.index(slot_id))

    def update_content(self, event=None, slot_index=None):
        if self.slot_ids:
            self.setEnabled(True)
            # update combobox
            self.comboBox_slots.blockSignals(True)
            if slot_index is None:
                slot_index = self.comboBox_slots.currentIndex()
                if slot_index > len(self.slot_ids) - 1 or slot_index < 0:
                    slot_index = len(self.slot_ids) - 1
            self.comboBox_slots.clear()
            self.comboBox_slots.addItems(self.slot_names)
            self.comboBox_slots.setCurrentIndex(slot_index)
            self.comboBox_slots.blockSignals(False)
            # populate content
            slot_state = self.pipeline.slots[slot_index].__getstate__()
            self.__setstate__(slot_state)
            self.on_ui_changed()
        else:
            self.setEnabled(False)

    def write_slot(self):
        """Update the shapeout2.pipeline.Dataslot instance"""
        # get current index
        slot_state = self.__getstate__()
        slot = self.pipeline.get_slot(slot_state["identifier"])
        # This is important, otherwise update_content will not have the
        # latest state.
        slot.__setstate__(slot_state)
        self.update_content()  # update slot combobox and visible fl names
        self.slot_changed.emit(slot_state)
