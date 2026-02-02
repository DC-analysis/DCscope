import importlib.resources

from PyQt6 import uic, QtCore, QtWidgets

from ..helpers import connect_pp_mod_signals


class BlockMatrix(QtWidgets.QWidget):
    pipeline_changed = QtCore.pyqtSignal(dict)

    filter_modify_clicked = QtCore.pyqtSignal(str)
    plot_modify_clicked = QtCore.pyqtSignal(str)
    slot_modify_clicked = QtCore.pyqtSignal(str)

    # widgets emit these whenever they changed the pipeline
    pp_mod_send = QtCore.pyqtSignal(dict)
    # widgets receive these so they can reflect the pipeline changes
    pp_mod_recv = QtCore.pyqtSignal(dict)

    def __init__(self, *args, **kwargs):
        """Helper class that wraps DataMatrix and PlotMatrix"""
        super(BlockMatrix, self).__init__(*args, **kwargs)
        ref = importlib.resources.files(
            "dcscope.gui.matrix") / "block_matrix.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        self.pipeline = None

        self._old_state = {}
        # Signals
        # DataMatrix
        self.data_matrix.pp_mod_send.connect(self.on_matrix_changed)
        self.data_matrix.filter_modify_clicked.connect(
            self.filter_modify_clicked)
        self.data_matrix.slot_modify_clicked.connect(self.slot_modify_clicked)
        # PlotMatrix
        self.plot_matrix.pp_mod_send.connect(self.on_matrix_changed)
        self.plot_matrix.plot_modify_clicked.connect(self.plot_modify_clicked)

        connect_pp_mod_signals(self, self.plot_matrix)
        connect_pp_mod_signals(self, self.data_matrix)

        self.setMouseTracking(True)

    # Qt widget overrides
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

    def mouseMoveEvent(self, e):
        p = self.mapToGlobal(e.pos())
        # Get the global position of the mouse event
        widget_under_mouse = QtWidgets.QApplication.widgetAt(p)

        QtWidgets.QToolTip.showText(e.pos(),
                                    widget_under_mouse.toolTip(),
                                    widget_under_mouse,
                                    msecShowTime=60000)

    def set_pipeline(self, pipeline):
        if self.pipeline is not None:
            raise ValueError("Pipeline can only be set once")
        self.pipeline = pipeline

        self.data_matrix.set_pipeline(self.pipeline)
        self.plot_matrix.set_pipeline(self.pipeline)

    def add_dataset(self, *args, **kwargs):
        self.data_matrix.add_dataset(*args, **kwargs)

    def add_filter(self, *args, **kwargs):
        self.data_matrix.add_filter(*args, **kwargs)

    def add_plot(self, *args, **kwargs):
        self.plot_matrix.add_plot(*args, **kwargs)

    def get_widget(self, slot_id=None, filt_plot_id=None):
        """Convenience function for testing"""
        if slot_id is None and filt_plot_id is not None:
            # get a filter or a plot
            w = self.data_matrix.filter_widgets + self.plot_matrix.plot_widgets
            for wi in w:
                if wi.identifier == filt_plot_id:
                    break
            else:
                raise KeyError(
                    "Widget identifier '{}' not found!".format(filt_plot_id))
            return wi
        elif slot_id is not None and filt_plot_id is None:
            # get a slot
            for wi in self.data_matrix.dataset_widgets:
                if wi.identifier == slot_id:
                    break
            else:
                raise KeyError(
                    "Widget identifier '{}' not found!".format(filt_plot_id))
            return wi
        elif slot_id is not None and filt_plot_id is not None:
            # get a matrix element
            wd = self.data_matrix.element_widget_dict
            wp = self.plot_matrix.element_widget_dict
            fpd = wd[slot_id]
            fpp = wp[slot_id]
            if filt_plot_id in fpp:
                wi = fpp[filt_plot_id]
            elif filt_plot_id in fpd:
                wi = fpd[filt_plot_id]
            else:
                raise KeyError(
                    "Widget identifier '{}' not found!".format(filt_plot_id))
            return wi
        else:
            raise ValueError(
                "At least one of `slot_id`, `filt_plot_id` must be specified!")

    def invalidate_elements(self, invalid_dm, invalid_pm):
        for slot_id, filt_id in invalid_dm:
            em = self.data_matrix.get_matrix_element(slot_id, filt_id)
            em.active = False
            em.invalid = True
            em.update_content()
        for slot_id, plot_id in invalid_pm:
            em = self.plot_matrix.get_matrix_element(slot_id, plot_id)
            em.active = False
            em.invalid = True
            em.update_content()

    def on_matrix_changed(self):
        state = self.pipeline.__getstate__()
        self.pipeline_changed.emit(state)

    def update(self, *args, **kwargs):
        self.scrollArea_block.update()
        super(BlockMatrix, self).update(*args, **kwargs)
