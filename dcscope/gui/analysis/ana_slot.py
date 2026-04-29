import warnings

import dclab
from dclab.features.emodulus.viscosity import (
    ALIAS_MEDIA, KNOWN_MEDIA, TemperatureOutOfRangeWarning
)
import numpy as np
from PyQt6 import QtCore, QtWidgets

from ... import meta_tool
from .ana_slot_ui import Ui_Form
from .dlg_slot_reorder import DlgSlotReorder


class SlotPanel(QtWidgets.QWidget):
    # widgets emit these whenever they changed the pipeline
    pp_mod_send = QtCore.pyqtSignal(dict)
    # widgets receive these so they can reflect the pipeline changes
    pp_mod_recv = QtCore.pyqtSignal(dict)

    def __init__(self, *args, **kwargs):
        super(SlotPanel, self).__init__(*args, **kwargs)

        self.ui = Ui_Form()
        self.ui.setupUi(self)

        # current DCscope pipeline
        self.pipeline = None

        # signals
        self.ui.toolButton_reorder.clicked.connect(self.on_reorder_slots)
        self.ui.toolButton_anew.clicked.connect(self.on_anew_slot)
        self.ui.toolButton_duplicate.clicked.connect(self.on_duplicate_slot)
        self.ui.toolButton_remove.clicked.connect(self.on_remove_slot)
        self.ui.pushButton_apply.clicked.connect(self.write_slot)
        self.ui.pushButton_reset.clicked.connect(self.update_content)
        self.ui.comboBox_slots.currentIndexChanged.connect(self.update_content)
        self.ui.comboBox_medium.currentIndexChanged.connect(self.on_ui_changed)
        self.ui.comboBox_temp.currentIndexChanged.connect(self.on_ui_changed)
        self.ui.comboBox_visc_model.currentIndexChanged.connect(
            self.on_ui_changed)
        self.ui.doubleSpinBox_temp.valueChanged.connect(self.on_ui_changed)
        # init
        self._update_emodulus_medium_choices()
        self._update_emodulus_temp_choices()
        self._update_emodulus_lut_choices()
        self._update_emodulus_visc_model_choices()

        self.pp_mod_recv.connect(self.on_pp_mod_recv)

    def read_pipeline_state(self):
        slot_state = self.current_slot_state
        if self.ui.comboBox_temp.currentData() in ["manual", "config"]:
            emod_temp = self.ui.doubleSpinBox_temp.value()
        else:
            emod_temp = np.nan
        if self.ui.comboBox_medium.currentData() in KNOWN_MEDIA:
            emod_visc = np.nan  # viscosity computed for known medium
            scenario = self.ui.comboBox_temp.currentData()
        elif self.ui.comboBox_medium.currentData() == "unknown":
            emod_visc = np.nan  # viscosity not defined
            scenario = None
        else:  # "other", user-defined medium
            emod_visc = self.ui.doubleSpinBox_visc.value()  # user input
            scenario = None
        emod_visc_model = self.ui.comboBox_visc_model.currentData()
        emod_select_lut = self.ui.comboBox_lut.currentText()
        state = {
            "identifier": slot_state["identifier"],
            "name": self.ui.lineEdit_name.text(),
            "path": slot_state["path"],
            "color": self.ui.pushButton_color.color().name(),
            "slot used": self.ui.checkBox_use.isChecked(),
            "fl names": {"FL-1": self.ui.lineEdit_fl1.text(),
                         "FL-2": self.ui.lineEdit_fl2.text(),
                         "FL-3": self.ui.lineEdit_fl3.text(),
                         },
            "crosstalk": {
                "crosstalk fl12": self.ui.doubleSpinBox_ct12.value(),
                "crosstalk fl13": self.ui.doubleSpinBox_ct13.value(),
                "crosstalk fl21": self.ui.doubleSpinBox_ct21.value(),
                "crosstalk fl23": self.ui.doubleSpinBox_ct23.value(),
                "crosstalk fl31": self.ui.doubleSpinBox_ct31.value(),
                "crosstalk fl32": self.ui.doubleSpinBox_ct32.value(),
            },
            "emodulus": {
                "emodulus enabled": slot_state["emodulus"]["emodulus enabled"],
                "emodulus lut": emod_select_lut,
                # It is ok if we have user-defined strings here, because
                # only media in KNOWN_MEDIA are passed to dclab in the end.
                "emodulus medium": self.ui.comboBox_medium.currentData(),
                "emodulus scenario": scenario,
                "emodulus temperature": emod_temp,
                "emodulus viscosity": emod_visc,
                "emodulus viscosity model": emod_visc_model,
            }
        }
        return state

    def write_pipeline_state(self, state):
        cur_state = self.current_slot_state
        if cur_state["identifier"] != state["identifier"]:
            raise ValueError("Slot identifier mismatch!")
        self.ui.lineEdit_name.setText(state["name"])
        self.ui.lineEdit_path.setText(str(state["path"]))
        self.ui.pushButton_color.setColor(state["color"])
        self.ui.lineEdit_fl1.setText(state["fl names"]["FL-1"])
        self.ui.lineEdit_fl2.setText(state["fl names"]["FL-2"])
        self.ui.lineEdit_fl3.setText(state["fl names"]["FL-3"])
        self.ui.checkBox_use.setChecked(state["slot used"])
        # crosstalk
        crosstalk = state["crosstalk"]
        self.ui.doubleSpinBox_ct12.setValue(crosstalk["crosstalk fl12"])
        self.ui.doubleSpinBox_ct13.setValue(crosstalk["crosstalk fl13"])
        self.ui.doubleSpinBox_ct21.setValue(crosstalk["crosstalk fl21"])
        self.ui.doubleSpinBox_ct23.setValue(crosstalk["crosstalk fl23"])
        self.ui.doubleSpinBox_ct31.setValue(crosstalk["crosstalk fl31"])
        self.ui.doubleSpinBox_ct32.setValue(crosstalk["crosstalk fl32"])
        # emodulus
        # updating the medium/temperature choices has to be done first,
        # because self.ui.comboBox_medium triggers the function on_ui_changed.
        self._update_emodulus_medium_choices()
        self._update_emodulus_temp_choices()
        emodulus = state["emodulus"]
        self.ui.groupBox_emod.setVisible(emodulus["emodulus enabled"])
        idx_med = self.ui.comboBox_medium.findData(emodulus["emodulus medium"])
        if idx_med == -1:  # empty medium string
            idx_med = self.ui.comboBox_medium.findData("other")
        self.ui.comboBox_medium.setCurrentIndex(idx_med)
        cfg = meta_tool.get_rtdc_config(state["path"])
        if "medium" in cfg["setup"] and cfg["setup"]["medium"] in KNOWN_MEDIA:
            self.ui.comboBox_medium.setEnabled(False)  # prevent modification
        else:
            self.ui.comboBox_medium.setEnabled(True)  # user-defined
        # https://dclab.readthedocs.io/en/latest/sec_av_emodulus.html
        scenario = emodulus.get("emodulus scenario", "manual")
        if scenario:
            idx_scen = self.ui.comboBox_temp.findData(scenario)
            self.ui.comboBox_temp.blockSignals(True)
            self.ui.comboBox_temp.setCurrentIndex(idx_scen)
            self.ui.comboBox_temp.blockSignals(False)

        idx_vm = self.ui.comboBox_visc_model.findData(
            # use defaults from previous session (Herold-2107)
            emodulus.get("emodulus viscosity model", "herold-2017"))

        self.ui.comboBox_visc_model.setCurrentIndex(idx_vm)
        # Set current state of the emodulus lut
        idx_lut = self.ui.comboBox_lut.findData(emodulus.get("emodulus lut", ""))
        self.ui.comboBox_lut.setCurrentIndex(idx_lut)
        # This has to be done after setting the scenario
        # (otherwise it might be overridden in the frontend)
        self.ui.doubleSpinBox_temp.setValue(emodulus["emodulus temperature"])
        self.ui.doubleSpinBox_visc.setValue(emodulus["emodulus viscosity"])

        # Fluorescence data visibility
        features = meta_tool.get_rtdc_features(state["path"])
        hasfl1 = "fl1_max" in features
        hasfl2 = "fl2_max" in features
        hasfl3 = "fl3_max" in features

        # labels
        self.ui.lineEdit_fl1.setVisible(hasfl1)
        self.ui.label_fl1.setVisible(hasfl1)
        self.ui.lineEdit_fl2.setVisible(hasfl2)
        self.ui.label_fl2.setVisible(hasfl2)
        self.ui.lineEdit_fl3.setVisible(hasfl3)
        self.ui.label_fl3.setVisible(hasfl3)

        # crosstalk matrix
        self.ui.label_from_fl1.setVisible(hasfl1 & hasfl2 | hasfl1 & hasfl3)
        self.ui.label_from_fl2.setVisible(hasfl2 & hasfl1 | hasfl2 & hasfl3)
        self.ui.label_from_fl3.setVisible(hasfl3 & hasfl1 | hasfl3 & hasfl2)
        self.ui.label_to_fl1.setVisible(hasfl1 & hasfl2 | hasfl1 & hasfl3)
        self.ui.label_to_fl2.setVisible(hasfl2 & hasfl1 | hasfl2 & hasfl3)
        self.ui.label_to_fl3.setVisible(hasfl3 & hasfl1 | hasfl3 & hasfl2)
        self.ui.doubleSpinBox_ct12.setVisible(hasfl1 & hasfl2)
        self.ui.doubleSpinBox_ct13.setVisible(hasfl1 & hasfl3)
        self.ui.doubleSpinBox_ct21.setVisible(hasfl2 & hasfl1)
        self.ui.doubleSpinBox_ct23.setVisible(hasfl2 & hasfl3)
        self.ui.doubleSpinBox_ct31.setVisible(hasfl3 & hasfl1)
        self.ui.doubleSpinBox_ct32.setVisible(hasfl3 & hasfl2)

        self.ui.groupBox_fl_labels.setVisible(hasfl1 | hasfl2 | hasfl3)
        self.ui.groupBox_fl_cross.setVisible(hasfl1 | hasfl2 | hasfl3)

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
        self.ui.comboBox_medium.blockSignals(True)
        self.ui.comboBox_medium.clear()
        ds = self.get_dataset()
        choices = self.get_dataset_choices_medium(ds)
        for name, data in choices:
            self.ui.comboBox_medium.addItem(name, data)
        self.ui.comboBox_medium.blockSignals(False)

    def _update_emodulus_temp_choices(self):
        """pupdate temperature choices for YM

        The previous selection is preserved. Signals are blocked.
        """
        self.ui.comboBox_temp.blockSignals(True)
        cursel = self.ui.comboBox_temp.currentData()
        self.ui.comboBox_temp.clear()
        ds = self.get_dataset()
        choices = self.get_dataset_choices_temperature(ds)
        for name, data in choices:
            self.ui.comboBox_temp.addItem(name, data)
        idx = self.ui.comboBox_temp.findData(cursel)
        self.ui.comboBox_temp.setCurrentIndex(idx)
        self.ui.comboBox_temp.blockSignals(False)

    def _update_emodulus_lut_choices(self):
        """update currently available LUT choices for YM

        The previous selection is preserved. Signals are blocked.
        """
        self.ui.comboBox_lut.blockSignals(True)
        cursel = self.ui.comboBox_lut.currentData()
        self.ui.comboBox_lut.clear()
        lut_dict = dclab.features.emodulus.load.get_internal_lut_names_dict()
        for lut_id in lut_dict.keys():
            self.ui.comboBox_lut.addItem(lut_id, lut_id)
        idx = self.ui.comboBox_lut.findData(cursel)
        self.ui.comboBox_lut.setCurrentIndex(idx)
        self.ui.comboBox_lut.blockSignals(False)

    def _update_emodulus_visc_model_choices(self):
        """update currently available viscosity model choices for YM

        Signals are blocked.
        """
        self.ui.comboBox_visc_model.blockSignals(True)
        self.ui.comboBox_visc_model.clear()

        choices = {"Herold (2017)": "herold-2017",
                   "Buyukurganci (2022)": "buyukurganci-2022"}
        for name, data in choices.items():
            self.ui.comboBox_visc_model.addItem(name, data)
        self.ui.comboBox_visc_model.blockSignals(False)

    @property
    def current_slot_state(self):
        if self.pipeline and self.pipeline.slots:
            slot_index = self.ui.comboBox_slots.currentIndex()
            slot_state = self.pipeline.slots[slot_index].__getstate__()
        else:
            slot_state = None
        return slot_state

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
            return self.pipeline.deduce_display_names()

    def get_dataset(self):
        """Return dataset associated with the current slot index

        Returns None if there is no dataset in the pipeline.
        """
        if self.pipeline is not None and self.pipeline.slots:
            slot_index = self.ui.comboBox_slots.currentIndex()
            slot = self.pipeline.slots[slot_index]
            return slot.get_dataset()
        else:
            return None

    @QtCore.pyqtSlot()
    def on_anew_slot(self):
        with self.pipeline.lock:
            slot_state = self.read_pipeline_state()
            pos = self.pipeline.slot_ids.index(slot_state["identifier"])
            new_id = self.pipeline.add_slot(path=slot_state["path"],
                                            index=pos + 1,
                                            )
        self.pp_mod_send.emit({"pipeline": {"slot_created": new_id}})

    @QtCore.pyqtSlot()
    def on_duplicate_slot(self):
        with self.pipeline.lock:
            # determine the new filter state
            slot_state = self.read_pipeline_state()
            new_id = self.pipeline.duplicate_slot(slot_state["identifier"])
        self.pp_mod_send.emit({"pipeline": {"slot_created": new_id}})

    @QtCore.pyqtSlot(dict)
    def on_pp_mod_recv(self, data):
        """We received a signal that something changed"""
        if data.get("pipeline"):
            if self.isVisible():
                self.update_content()

    @QtCore.pyqtSlot()
    def on_remove_slot(self):
        with self.pipeline.lock:
            slot_state = self.read_pipeline_state()
            slot_id = slot_state["identifier"]
            self.pipeline.remove_slot(slot_id)
        self.pp_mod_send.emit({"pipeline": {"slot_created": slot_id}})

    @QtCore.pyqtSlot()
    def on_reorder_slots(self):
        """Open dialog for reordering slots"""
        dlg = DlgSlotReorder(self.pipeline, self)
        dlg.pp_mod_send.connect(self.pp_mod_send)
        dlg.exec()

    @QtCore.pyqtSlot()
    def on_ui_changed(self):
        """Called when the user m
        index: int
            index of the slot in the pipeline;
            indexing starts at "0".odifies the medium or temperature options"""
        medium = self.ui.comboBox_medium.currentData()
        tselec = self.ui.comboBox_temp.currentData()
        medium_key = ALIAS_MEDIA.get(medium, medium)
        visc_model = self.ui.comboBox_visc_model.currentData()
        # Only show model selection if we are dealing with MC-PBS
        self.ui.comboBox_visc_model.setVisible(medium_key.count("MC-PBS"))
        self.ui.doubleSpinBox_visc.setStyleSheet("")
        if medium in KNOWN_MEDIA:  # medium registered with dclab
            self.ui.label_temp.setVisible(True)
            self.ui.comboBox_temp.setVisible(True)
            self.ui.doubleSpinBox_temp.setVisible(True)
            self.ui.comboBox_temp.setEnabled(True)
            self.ui.doubleSpinBox_visc.setEnabled(True)
            self.ui.doubleSpinBox_visc.setReadOnly(True)
            if tselec == "manual":
                temperature = self.ui.doubleSpinBox_temp.value()
                self.ui.doubleSpinBox_temp.setEnabled(True)
                self.ui.doubleSpinBox_temp.setReadOnly(False)
            elif tselec == "config":
                # get temperature from dataset
                ds = self.get_dataset()
                temperature = ds.config["setup"]["temperature"]
                self.ui.doubleSpinBox_temp.setEnabled(True)
                self.ui.doubleSpinBox_temp.setReadOnly(True)
                self.ui.doubleSpinBox_temp.setValue(temperature)
            elif tselec == "feature":
                temperature = np.nan
                self.ui.doubleSpinBox_temp.setEnabled(False)
                self.ui.doubleSpinBox_temp.setVisible(False)
                self.ui.doubleSpinBox_temp.setValue(temperature)
            else:
                assert tselec is None, "We should still be in init"
                return
            # For user convenience, also show the viscosity
            if medium in KNOWN_MEDIA and not np.isnan(temperature):
                # compute viscosity
                state = self.read_pipeline_state()
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
                self.ui.doubleSpinBox_visc.setVisible(True)
                self.ui.doubleSpinBox_visc.setEnabled(True)
                self.ui.doubleSpinBox_visc.setReadOnly(True)
                self.ui.doubleSpinBox_visc.setValue(visc)
                self.ui.doubleSpinBox_visc.setStyleSheet(vstyle)
            else:
                self.ui.doubleSpinBox_visc.setEnabled(False)
                self.ui.doubleSpinBox_visc.setVisible(False)
                self.ui.doubleSpinBox_visc.setReadOnly(True)
                self.ui.doubleSpinBox_visc.setValue(np.nan)
        elif medium == "undefined":
            self.ui.label_temp.setVisible(False)
            self.ui.comboBox_temp.setVisible(False)
            self.ui.doubleSpinBox_temp.setVisible(False)
            self.ui.doubleSpinBox_temp.setEnabled(False)
            self.ui.doubleSpinBox_temp.setValue(np.nan)
            self.ui.doubleSpinBox_visc.setValue(np.nan)
            self.ui.doubleSpinBox_visc.setEnabled(False)
        else:  # "other" or user-defined
            self.ui.label_temp.setVisible(False)
            self.ui.comboBox_temp.setVisible(False)
            self.ui.doubleSpinBox_temp.setVisible(False)
            self.ui.doubleSpinBox_temp.setEnabled(False)
            self.ui.doubleSpinBox_temp.setValue(np.nan)
            self.ui.doubleSpinBox_visc.setEnabled(True)
            self.ui.doubleSpinBox_visc.setReadOnly(False)

    def set_pipeline(self, pipeline):
        if self.pipeline is not None:
            raise ValueError("Pipeline can only be set once")
        self.pipeline = pipeline

    def show_slot(self, slot_id):
        self.update_content(slot_index=self.slot_ids.index(slot_id))

    def update_content(self, slot_index=None, **kwargs):
        if self.slot_ids:
            # remember the previous slot index and make sure it is sane
            prev_index = self.ui.comboBox_slots.currentIndex()
            if prev_index is None or prev_index < 0:
                prev_index = len(self.slot_ids) - 1

            self.setEnabled(True)
            # update combobox
            self.ui.comboBox_slots.blockSignals(True)
            if slot_index is None or slot_index < 0:
                slot_index = prev_index
            slot_index = min(slot_index, len(self.slot_ids) - 1)

            self.ui.comboBox_slots.clear()
            self.ui.comboBox_slots.addItems(self.slot_names)
            self.ui.comboBox_slots.setCurrentIndex(slot_index)
            self.ui.comboBox_slots.blockSignals(False)
            # populate content
            slot_state = self.pipeline.slots[slot_index].__getstate__()
            self.write_pipeline_state(slot_state)
            self.on_ui_changed()
        else:
            self.setEnabled(False)

    def write_slot(self):
        """Update the dcscope.pipeline.Dataslot instance"""
        with self.pipeline.lock:
            slot_state = self.read_pipeline_state()
            slot_id = slot_state["identifier"]
            slot_index = self.pipeline.slot_ids.index(slot_id)
            self.pipeline.slots[slot_index].__setstate__(slot_state)
        self.pp_mod_send.emit({"pipeline": {"slot_changed": slot_id}})
