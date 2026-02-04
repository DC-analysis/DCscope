import importlib.resources

from PyQt6 import uic, QtWidgets, QtCore


class PlotMatrixElement(QtWidgets.QWidget):
    # widgets emit these whenever they changed the pipeline
    pp_mod_send = QtCore.pyqtSignal(dict)
    # widgets receive these so they can reflect the pipeline changes
    pp_mod_recv = QtCore.pyqtSignal(dict)

    def __init__(self, pipeline, slot_index, plot_index, *args, **kwargs):
        super(PlotMatrixElement, self).__init__(*args, **kwargs)
        ref = importlib.resources.files(
            "dcscope.gui.matrix") / "dm_element.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        self.pipeline = pipeline

        self.slot_index = slot_index
        self.plot_index = plot_index

        self.active = False
        self.enabled = True

        self.update_content()

        # signal received
        self.pp_mod_recv.connect(self.on_pp_mod_recv)

    # Properties
    @property
    def invalid(self):
        return not self.pipeline.is_element_valid(
            slot_id=self.pipeline.slot_ids[self.slot_index],
            filt_plot_id=self.pipeline.plot_ids[self.plot_index]
        )

    # Other methods
    def abolish(self):
        self.pp_mod_send.disconnect()
        self.pp_mod_recv.disconnect()
        self.hide()
        self.deleteLater()

    def mousePressEvent(self, event):
        # toggle selection
        if not self.invalid:
            # Activate or deactivate this plot
            with self.pipeline.lock:
                slot_id = self.pipeline.slot_ids[self.slot_index]
                plot_id = self.pipeline.plot_ids[self.plot_index]
                self.pipeline.set_element_active(
                    slot_id,
                    plot_id,
                    not self.invalid and not self.active)
                self.pp_mod_send.emit(
                    {"pipeline": {"plot_change": plot_id}})
            event.accept()

    @QtCore.pyqtSlot(dict)
    def on_pp_mod_recv(self, data: dict):
        pp_dict = data.get("pipeline", {})
        if pp_dict:
            slot_id = self.pipeline.slot_ids[self.slot_index]
            plot_id = self.pipeline.plot_ids[self.plot_index]
            state = {
                "active": self.pipeline.element_states[slot_id][plot_id],
                "enabled": self.pipeline.slots[self.slot_index].slot_used,
            }
            self.write_pipeline_state(state)

    def read_pipeline_state(self):
        state = {"active": self.active,
                 "enabled": self.enabled,
                 }
        return state

    def write_pipeline_state(self, state):
        self.active = state["active"]
        self.enabled = state["enabled"]
        self.update_content()

    def update_content(self):
        if self.invalid:
            color = "#DCDCDC"  # gray
            label = "invalid"
            tooltip = "Incompatible plot settings"
        elif self.active and self.enabled:
            color = "#86E7C1"  # turquois
            label = "active"
            tooltip = "Click to deactivate"
        elif self.active and not self.enabled:
            color = "#C9DAD7"  # gray-turquois
            label = "active\n(unused)"
            tooltip = "Click to deactivate"
        elif not self.active and self.enabled:
            color = "#EFEFEF"  # light gray
            label = "inactive"
            tooltip = "Click to activate"
        else:
            color = "#DCDCDC"  # gray
            label = "inactive\n(unused)"
            tooltip = "Click to activate"

        self.label.setText(label)
        self.setToolTip(tooltip)
        self.label.setToolTip(tooltip)
        self.setStyleSheet(
            "background-color:{};color:black".format(color))
