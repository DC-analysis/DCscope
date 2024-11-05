import copy
import importlib.resources

from PyQt6 import uic, QtCore, QtWidgets


class BlockMatrix(QtWidgets.QWidget):
    pipeline_changed = QtCore.pyqtSignal(dict)
    quickviewed = QtCore.pyqtSignal(int, int)

    filter_modify_clicked = QtCore.pyqtSignal(str)
    plot_modify_clicked = QtCore.pyqtSignal(str)
    slot_modify_clicked = QtCore.pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        """Helper class that wraps DataMatrix and PlotMatrix"""
        super(BlockMatrix, self).__init__(*args, **kwargs)
        ref = importlib.resources.files(
            "shapeout2.gui.matrix") / "block_matrix.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        self._old_state = {}
        # Signals
        # DataMatrix
        self.data_matrix.matrix_changed.connect(self.on_matrix_changed)
        self.data_matrix.filter_modify_clicked.connect(
            self.filter_modify_clicked)
        self.data_matrix.slot_modify_clicked.connect(self.slot_modify_clicked)
        self.data_matrix.quickviewed.connect(self.quickviewed)
        # PlotMatrix
        self.plot_matrix.matrix_changed.connect(self.on_matrix_changed)
        self.plot_matrix.plot_modify_clicked.connect(self.plot_modify_clicked)

    def __getstate__(self):
        state = self.data_matrix.__getstate__()
        statep = self.plot_matrix.__getstate__()
        state["plots"] = statep["plots"]
        for ss in statep["elements"]:
            for plot in statep["elements"][ss]:
                state["elements"][ss][plot] = statep["elements"][ss][plot]
        return state

    def __setstate__(self, state):
        # DataMatrix
        stated = copy.deepcopy(state)
        stated.pop("plots")
        for slot_state in state["slots"]:
            slot_id = slot_state["identifier"]
            for plot_state in state["plots"]:
                plot_id = plot_state["identifier"]
                stated["elements"][slot_id].pop(plot_id)
        self.data_matrix.__setstate__(stated)
        # PlotMatrix
        statep = copy.deepcopy(state)
        statep.pop("filters")
        statep.pop("filters used")
        statep.pop("slots used")
        for slot_state in state["slots"]:
            slot_id = slot_state["identifier"]
            for filt_state in state["filters"]:
                filt_id = filt_state["identifier"]
                statep["elements"][slot_id].pop(filt_id)
        self.plot_matrix.__setstate__(statep)

    def add_dataset(self, *args, **kwargs):
        self.data_matrix.add_dataset(*args, **kwargs)

    def add_filter(self, *args, **kwargs):
        self.data_matrix.add_filter(*args, **kwargs)

    def add_plot(self, *args, **kwargs):
        self.plot_matrix.add_plot(*args, **kwargs)

    def adopt_pipeline(self, pipeline_state):
        self.__setstate__(pipeline_state)

    def enable_quickview(self, view):
        self.data_matrix.enable_quickview(view)

    def get_quickview_indices(self):
        return self.data_matrix.get_quickview_indices()

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
        state = self.__getstate__()
        self.pipeline_changed.emit(state)

    def update(self, *args, **kwargs):
        self.scrollArea_block.update()
        super(BlockMatrix, self).update(*args, **kwargs)
