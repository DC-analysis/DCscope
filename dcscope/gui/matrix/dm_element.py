import importlib.resources

from PyQt6 import uic, QtWidgets, QtCore


class DataMatrixElement(QtWidgets.QWidget):
    # widgets emit these whenever they changed the pipeline
    pp_mod_send = QtCore.pyqtSignal(dict)
    # widgets receive these so they can reflect the pipeline changes
    pp_mod_recv = QtCore.pyqtSignal(dict)

    def __init__(self, pipeline, slot_index, filt_index, *args, **kwargs):
        super(DataMatrixElement, self).__init__(*args, **kwargs)
        ref = importlib.resources.files(
            "dcscope.gui.matrix") / "dm_element.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        self.pipeline = pipeline

        self.slot_index = slot_index
        self.filt_index = filt_index

        self.active = False
        self.enabled = True
        self.quickview = False
        self.quickview_dict = None

        self.setMouseTracking(True)

        # signal received
        self.pp_mod_recv.connect(self.on_pp_mod_recv)

    # Qt method overrides
    def mousePressEvent(self, event):
        # toggle selection
        if not self.invalid:
            if event.modifiers() == QtCore.Qt.KeyboardModifier.ShiftModifier:
                # Let everyone know that this widget gets quickview
                qv_dict = {
                    "slot_index": self.slot_index,
                    "slot_id": self.pipeline.slot_ids[self.slot_index],
                    "filt_index": self.filt_index,
                    "filt_id": self.pipeline.filter_ids[self.filt_index],
                    }
                self.pp_mod_send.emit({"quickview": qv_dict})
            else:
                # Activate or deactivate this filter
                with self.pipeline.lock:
                    slot_id = self.pipeline.slot_ids[self.slot_index]
                    filter_id = self.pipeline.filter_ids[self.filt_index]
                    self.pipeline.set_element_active(slot_id,
                                                     filter_id,
                                                     not self.active)
                    self.pp_mod_send.emit(
                        {"pipeline": {"filter_ray_change": slot_id}})

            event.accept()

    def setMouseTracking(self, flag):
        """Set mouse tracking recursively

        This is necessary for `BlockMatrix.mouseMoveEvent` to work
        throughout its children.
        """
        def recursive_set(parent):
            for child in parent.findChildren(QtCore.QObject):
                try:
                    child.setMouseTracking(flag)
                except BaseException:
                    pass
                recursive_set(child)
        QtWidgets.QWidget.setMouseTracking(self, flag)
        recursive_set(self)

    # Properties
    @property
    def invalid(self):
        return not self.pipeline.is_element_valid(
            slot_id=self.pipeline.slot_ids[self.slot_index],
            filt_plot_id=self.pipeline.filter_ids[self.filt_index]
        )

    # Other methods
    def abolish(self):
        self.pp_mod_send.disconnect()
        self.pp_mod_recv.disconnect()
        self.hide()
        self.deleteLater()

    @QtCore.pyqtSlot(dict)
    def on_pp_mod_recv(self, data: dict):
        qv_dict = data.get("quickview", {})

        if qv_dict:
            # every instance must know where quick view is set
            self.quickview_dict = qv_dict

        pp_dict = data.get("pipeline", {})
        if pp_dict or qv_dict:
            slot_id = self.pipeline.slot_ids[self.slot_index]
            filter_id = self.pipeline.filter_ids[self.filt_index]
            state = {
                "active": self.pipeline.element_states[slot_id][filter_id],
                "enabled": (
                    self.pipeline.filters[self.filt_index].filter_used
                    and self.pipeline.slots[self.slot_index].slot_used
                ),
            }

            if state != self.read_pipeline_state():
                self.write_pipeline_state(state)

            if self.quickview_dict:
                # Determine whether we have the QuickView
                is_quickview = (filter_id == self.quickview_dict["filt_id"]
                                and slot_id == self.quickview_dict["slot_id"])

                if is_quickview != self.quickview:
                    self.quickview = is_quickview
                    self.update_content()

    def read_pipeline_state(self):
        state = {"active": self.active and not self.invalid,
                 "enabled": self.enabled}
        return state

    def write_pipeline_state(self, state):
        self.active = state["active"]
        self.enabled = state["enabled"]
        self.update_content()

    def set_active(self, b=True):
        state = self.read_pipeline_state()
        state["active"] = b
        self.write_pipeline_state(state)

    def update_content(self):
        if self.invalid:
            color = "#DCDCDC"  # gray
            label = "invalid"
            tooltip = "Incompatible filter settings"
        elif self.active and self.enabled:
            color = "#86E789"  # green
            label = "active"
            tooltip = "Click to deactivate"
        elif self.active and not self.enabled:
            color = "#C9DAC9"  # gray-green
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

        if not self.invalid:
            if self.quickview:
                color = "#F0A1D6"
                label += "\n(QV)"
            else:
                tooltip += "\nShift+Click for Quick View"

        self.label.setText(label)
        self.setToolTip(tooltip)
        self.label.setToolTip(tooltip)
        self.setStyleSheet(f"background-color:{color};color:black")
