import copy
import importlib.resources

from PyQt6 import uic, QtWidgets, QtCore, QtGui

from ... import meta_tool


class MatrixDataset(QtWidgets.QWidget):
    modify_clicked = QtCore.pyqtSignal(str)

    # widgets emit these whenever they changed the pipeline
    pp_mod_send = QtCore.pyqtSignal(dict)
    # widgets receive these so they can reflect the pipeline changes
    pp_mod_recv = QtCore.pyqtSignal(dict)

    def __init__(self, pipeline, slot_index, *args, **kwargs):
        """Create a new dataset matrix element"""
        super(MatrixDataset, self).__init__(*args, **kwargs)
        ref = importlib.resources.files(
            "dcscope.gui.matrix") / "dm_dataset.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        self.pipeline = pipeline
        self.slot_index = slot_index
        self.path = None
        self.identifier = None
        self.active = False

        # options button
        menu = QtWidgets.QMenu()
        menu.addAction('insert anew', self.action_insert_anew)
        menu.addAction('duplicate', self.action_duplicate)
        menu.addAction('remove', self.action_remove)
        self.toolButton_opt.setMenu(menu)

        # toggle all active, all inactive, semi state
        self.toolButton_toggle.clicked.connect(self.on_active_toggled)

        # toggle enabled/disabled state
        self.checkBox.clicked.connect(self.on_enabled_toggled)

        # modify slot button
        self.toolButton_modify.clicked.connect(self.on_modify)

        # signal received
        self.pp_mod_recv.connect(self.on_pp_mod_recv)

        self.setMouseTracking(True)

    # Qt method overrides
    def setMouseTracking(self, flag):
        def recursive_set(parent):
            for child in parent.findChildren(QtCore.QObject):
                try:
                    child.setMouseTracking(flag)
                except BaseException:
                    pass
                recursive_set(child)
        QtWidgets.QWidget.setMouseTracking(self, flag)
        recursive_set(self)

    # Other methods
    def abolish(self):
        self.pp_mod_send.disconnect()
        self.pp_mod_recv.disconnect()
        self.modify_clicked.disconnect()
        self.hide()
        self.deleteLater()

    def action_duplicate(self):
        with self.pipeline.lock:
            slot = self.pipeline.slots[self.slot_index]
            new_id = self.pipeline.add_slot(
                path=self.path,
                index=self.slot_index+1)
            # use original state
            new_state = copy.deepcopy(
                self.pipeline.get_slot(slot.identifier).__getstate__())
            # only set the new identifier (issue #96)
            new_state["identifier"] = new_id
            self.pipeline.get_slot(new_id).__setstate__(new_state)
            self.pp_mod_send.emit({"pipeline": {"slot_created": new_id}})

    def action_insert_anew(self):
        with self.pipeline.lock:
            new_id = self.pipeline.add_slot(
                path=self.path,
                index=self.slot_index+1)
            self.pp_mod_send.emit({"pipeline": {"slot_created": new_id}})

    def action_remove(self):
        with self.pipeline.lock:
            slot_id = self.pipeline.slot_ids[self.slot_index]
            self.pipeline.remove_slot(slot_id)
            self.pp_mod_send.emit({"pipeline": {"slot_removed": slot_id}})

    @QtCore.pyqtSlot()
    def on_active_toggled(self):
        self.active = not self.active
        slot_id = self.pipeline.slot_ids[self.slot_index]

        with self.pipeline.lock:
            for filter_id in self.pipeline.filter_ids:
                self.pipeline.set_element_active(
                    slot_id=slot_id,
                    filt_plot_id=filter_id,
                    active=self.active
                )

            for plot_id in self.pipeline.plot_ids:
                self.pipeline.set_element_active(
                    slot_id=slot_id,
                    filt_plot_id=plot_id,
                    active=self.active
                )

            self.pp_mod_send.emit({"pipeline": {"slot_toggled": slot_id}})

    def on_enabled_toggled(self, b):
        with self.pipeline.lock:
            self.pipeline.slots[self.slot_index].slot_used = b
            state = "enabled" if b else "disabled"
            self.pp_mod_send.emit({"pipeline": {f"slot {state}": b}})

    def on_modify(self):
        self.modify_clicked.emit(self.identifier)

    @QtCore.pyqtSlot(dict)
    def on_pp_mod_recv(self, data: dict):
        pp_dict = data.get("pipeline", {})
        if pp_dict:
            # full slot pipeline state
            state = self.pipeline.slots[self.slot_index].__getstate__()
            # widget state
            wd_state = self.read_pipeline_state()
            # pipeline state with same keys as widget state
            pp_state = {k: state[k] for k in wd_state.keys()}
            if wd_state != pp_state:
                self.write_pipeline_state(pp_state)

    def read_pipeline_state(self):
        state = {"path": self.path,
                 "identifier": self.identifier,
                 "slot used": self.checkBox.isChecked(),
                 }
        return state

    def write_pipeline_state(self, state):
        self.identifier = state["identifier"]
        self.path = state["path"]
        self.checkBox.setChecked(state["slot used"])
        self.update_content()

    def set_label_string(self, string):
        if self.label.fontMetrics().boundingRect(string).width() < 65:
            nstring = string
        else:
            nstring = string + "..."
            while True:
                width = self.label.fontMetrics().boundingRect(nstring).width()
                if width > 65:
                    nstring = nstring[:-4] + "..."
                else:
                    break
        self.label.setText(nstring)

    def update_content(self):
        """Reset tool tips and title"""
        if self.path is not None:
            tip = meta_tool.get_repr(self.path, append_path=True)
            self.setToolTip(tip)
            self.label.setToolTip(tip)
            slot_index = self.pipeline.slot_ids.index(self.identifier)
            name = self.pipeline.reduced_sample_names[slot_index]
            self.set_label_string(name)
            # Set region image
            region = meta_tool.get_info(self.path,
                                        section="setup",
                                        key="chip region")
            icon = QtGui.QIcon.fromTheme("region_{}".format(region))
            pixmap = icon.pixmap(16)
            self.label_region.setPixmap(pixmap)
            self.label_region.setToolTip(region)
            if region == "channel":
                # Set flow rate
                flow_rate = meta_tool.get_info(self.path,
                                               section="setup",
                                               key="flow rate")
                self.label_flowrate.setText("{:.4g}".format(flow_rate))
                self.label_flowrate.setToolTip("{:.4g} µL/s".format(flow_rate))
            else:
                self.label_flowrate.setText(region[:3])
                self.label_flowrate.setToolTip(region)
