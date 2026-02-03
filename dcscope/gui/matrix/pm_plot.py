import importlib.resources

from PyQt6 import uic, QtCore, QtWidgets


class MatrixPlot(QtWidgets.QWidget):
    modify_clicked = QtCore.pyqtSignal(str)

    # widgets emit these whenever they changed the pipeline
    pp_mod_send = QtCore.pyqtSignal(dict)
    # widgets receive these so they can reflect the pipeline changes
    pp_mod_recv = QtCore.pyqtSignal(dict)

    def __init__(self, pipeline, plot_index, *args, **kwargs):
        super(MatrixPlot, self).__init__(*args, **kwargs)
        ref = importlib.resources.files("dcscope.gui.matrix") / "pm_plot.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        self.pipeline = pipeline
        self.plot_index = plot_index
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

    @QtCore.pyqtSlot()
    def on_active_toggled(self):
        self.active = not self.active
        plot_id = self.pipeline.plot_ids[self.plot_index]
        with self.pipeline.lock:
            for slot_id in self.pipeline.slot_ids:
                self.pipeline.set_element_active(
                    slot_id=slot_id,
                    filt_plot_id=plot_id,
                    active=self.active
                )
            self.pp_mod_send.emit({"pipeline": {"plot_toggled": plot_id}})

    # Other methods
    def abolish(self):
        self.pp_mod_send.disconnect()
        self.pp_mod_recv.disconnect()
        self.modify_clicked.disconnect()
        self.hide()
        self.deleteLater()

    @QtCore.pyqtSlot(dict)
    def on_pp_mod_recv(self, data: dict):
        pp_dict = data.get("pipeline", {})
        if pp_dict:
            state = self.pipeline.plots[self.plot_index].__getstate__()
            # widget state
            wd_state = self.read_pipeline_state()
            # pipeline state with same keys as widget state
            pp_state = {"name": state["layout"]["name"],
                        "identifier": state["identifier"]}
            if wd_state != pp_state:
                self.write_pipeline_state(pp_state)

    def read_pipeline_state(self):
        state = {"name": self.name,
                 "identifier": self.identifier,
                 }
        return state

    def write_pipeline_state(self, state):
        self.identifier = state["identifier"]
        self.name = state["name"]
        self.update_content()

    def action_duplicate(self):
        with self.pipeline.lock:
            plot_id = self.pipeline.plot_ids[self.plot_index]
            new_id = self.pipeline.duplicate_plot(plot_id)
            self.pp_mod_send.emit({"pipeline": {"plot_created": new_id}})

    def action_remove(self):
        with self.pipeline.lock:
            plot_id = self.pipeline.plot_ids[self.plot_index]
            self.pipeline.remove_plot(plot_id)
            self.pp_mod_send.emit({"pipeline": {"plot_removed": plot_id}})

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

    @QtCore.pyqtSlot()
    def update_content(self):
        """Reset tool tips and title"""
        self.label.setToolTip(self.name)
        self.set_label_string(self.name)
        self.update()
