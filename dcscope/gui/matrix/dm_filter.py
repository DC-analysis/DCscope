import importlib.resources

from PyQt6 import uic, QtCore, QtWidgets


class MatrixFilter(QtWidgets.QWidget):
    modify_clicked = QtCore.pyqtSignal(str)

    # widgets emit these whenever they changed the pipeline
    pp_mod_send = QtCore.pyqtSignal(dict)
    # widgets receive these so they can reflect the pipeline changes
    pp_mod_recv = QtCore.pyqtSignal(dict)

    def __init__(self, pipeline, filt_index, *args, **kwargs):
        super(MatrixFilter, self).__init__(*args, **kwargs)
        ref = importlib.resources.files(
            "dcscope.gui.matrix") / "dm_filter.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        self.pipeline = pipeline
        self.filt_index = filt_index

        self.identifier = None
        self.name = None
        self.active = False

        # options button
        menu = QtWidgets.QMenu()
        menu.addAction('duplicate', self.action_duplicate)
        menu.addAction('remove', self.action_remove)
        self.toolButton_opt.setMenu(menu)

        # toggle all active, all inactive, semi state
        self.toolButton_toggle.clicked.connect(self.on_active_toggled)

        # toggle enabled/disabled state
        self.checkBox.clicked.connect(self.on_enabled_toggled)

        # modify filter button
        self.toolButton_modify.clicked.connect(self.on_modify)

        self.setMouseTracking(True)

        # signal received
        self.pp_mod_recv.connect(self.on_pp_mod_recv)

    # Qt method overrides
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

    # Other methods
    def abolish(self):
        self.pp_mod_send.disconnect()
        self.pp_mod_recv.disconnect()
        self.modify_clicked.disconnect()
        self.hide()
        self.deleteLater()

    @QtCore.pyqtSlot()
    def on_active_toggled(self):
        self.active = not self.active
        filter_id = self.pipeline.filter_ids[self.filt_index]
        with self.pipeline.lock:
            for slot_id in self.pipeline.slot_ids:
                self.pipeline.set_element_active(
                    slot_id=slot_id,
                    filt_plot_id=filter_id,
                    active=self.active
                )
            self.pp_mod_send.emit({"pipeline": {"filter_toggled": filter_id}})

    @QtCore.pyqtSlot(dict)
    def on_pp_mod_recv(self, data: dict):
        pp_dict = data.get("pipeline", {})
        if pp_dict:
            state = self.pipeline.filters[self.filt_index].__getstate__()
            # widget state
            wd_state = self.read_pipeline_state()
            # pipeline state with same keys as widget state
            pp_state = {k: state[k] for k in wd_state.keys()}
            if wd_state != pp_state:
                self.write_pipeline_state(pp_state)

    def read_pipeline_state(self):
        state = {"filter used": self.checkBox.isChecked(),
                 "identifier": self.identifier,
                 "name": self.name,
                 }
        return state

    def write_pipeline_state(self, state):
        self.identifier = state["identifier"]
        self.name = state["name"]

        self.label.setToolTip(self.name)
        self.set_label_string(self.name)
        self.checkBox.blockSignals(True)
        self.checkBox.setChecked(state["filter used"])
        self.checkBox.blockSignals(False)

    def action_duplicate(self):
        with self.pipeline.lock:
            filt_id = self.pipeline.filter_ids[self.filt_index]
            new_id = self.pipeline.duplicate_filter(filt_id)
            self.pp_mod_send.emit({"pipeline": {"filter_added": new_id}})

    def action_remove(self):
        with self.pipeline.lock:
            filter_id = self.pipeline.filter_ids[self.filt_index]
            self.pipeline.remove_filter(filter_id)
            self.pp_mod_send.emit({"pipeline": {"filter_removed": filter_id}})

    def on_enabled_toggled(self, b):
        with self.pipeline.lock:
            self.pipeline.filters[self.filt_index].filter_used = b
            state = "enabled" if b else "disabled"
            self.pp_mod_send.emit({"pipeline": {f"filter {state}": b}})

    def on_modify(self):
        self.modify_clicked.emit(self.identifier)

    def set_label_string(self, string):
        if self.label.fontMetrics().boundingRect(string).width() < 60:
            nstring = string
        else:
            nstring = string + "..."
            while True:
                width = self.label.fontMetrics().boundingRect(nstring).width()
                if width > 60:
                    nstring = nstring[:-4] + "..."
                else:
                    break
        self.label.setText(nstring)
