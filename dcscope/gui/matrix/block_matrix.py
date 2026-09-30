from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ..helpers import connect_pp_mod_signals
from ...pipeline import Pipeline
from .block_matrix_ui import Ui_Form


class BlockMatrix(QtWidgets.QWidget):
    filter_modify_clicked = QtCore.pyqtSignal(str)
    plot_modify_clicked = QtCore.pyqtSignal(str)
    slot_modify_clicked = QtCore.pyqtSignal(str)

    # widgets emit these whenever they changed the pipeline
    pp_mod_send = QtCore.pyqtSignal(dict)
    # widgets receive these so they can reflect the pipeline changes
    pp_mod_recv = QtCore.pyqtSignal(dict)

    def __init__(self, *args, **kwargs):
        """Helper class that wraps DataMatrix and PlotMatrix"""
        super().__init__(*args, **kwargs)

        self.ui = Ui_Form()
        self.ui.setupUi(self)

        self.pipeline: Pipeline = None  # type: ignore

        # Signals
        # DataMatrix buttons
        self.ui.data_matrix.filter_modify_clicked.connect(
            self.filter_modify_clicked)
        self.ui.data_matrix.slot_modify_clicked.connect(
            self.slot_modify_clicked)
        # PlotMatrix buttons
        self.ui.plot_matrix.plot_modify_clicked.connect(
            self.plot_modify_clicked)
        # Other widgets

        # plot matrix must be connected after filter matrix (geometry updates)
        connect_pp_mod_signals(self, self.ui.data_matrix)
        connect_pp_mod_signals(self, self.ui.plot_matrix)
        self.pp_mod_recv.connect(self.on_pp_mod_recv)

        self.setMouseTracking(True)

    # Qt widget overrides
    def setMouseTracking(self, enable):
        """Set mouse tracking recursively

        This is necessary for `BlockMatrix.mouseMoveEvent` to work
        throughout its children.
        """
        def recursive_set(parent):
            for child in parent.findChildren(QtCore.QObject):
                try:
                    child.setMouseTracking(enable)
                except BaseException:
                    pass
                recursive_set(child)
        QtWidgets.QWidget.setMouseTracking(self, enable)
        recursive_set(self)

    def mouseMoveEvent(self, a0):
        if a0 is not None:
            p = self.mapToGlobal(a0.pos())
            # Get the global position of the mouse event
            widget_under_mouse = QtWidgets.QApplication.widgetAt(p)

            if widget_under_mouse is not None:
                QtWidgets.QToolTip.showText(a0.pos(),
                                            widget_under_mouse.toolTip(),
                                            widget_under_mouse,
                                            msecShowTime=60000)

    @QtCore.pyqtSlot(dict)
    def on_pp_mod_recv(self, data):
        if data.get("pipeline"):
            # Enable plot button
            if self.pipeline.slots:
                self.ui.toolButton_new_plot.setEnabled(True)
            else:
                self.ui.toolButton_new_plot.setEnabled(False)

        if data.get("block_matrix"):
            # Workaound: If this is not set, then the slot matrix element
            # is resized, but its sizer is not. Sending the signal twice
            # resolves the issue.
            self.ui.data_matrix.pp_mod_recv.emit(data)

    def set_pipeline(self, pipeline):
        if self.pipeline is not None:
            raise ValueError("Pipeline can only be set once")
        self.pipeline = pipeline

        self.ui.data_matrix.set_pipeline(self.pipeline)
        self.ui.plot_matrix.set_pipeline(self.pipeline)

    def get_widget(self, slot_id=None, filt_plot_id=None):
        """Convenience function for testing"""
        if slot_id is None and filt_plot_id is not None:
            # get a filter or a plot
            w = (self.ui.data_matrix.filter_widgets
                 + self.ui.plot_matrix.plot_widgets)
            for wi in w:
                if wi.identifier == filt_plot_id:
                    break
            else:
                raise KeyError(
                    f"Widget identifier '{filt_plot_id}' not found!")
            return wi
        elif slot_id is not None and filt_plot_id is None:
            # get a slot
            for wi in self.ui.data_matrix.dataset_widgets:
                if wi.identifier == slot_id:
                    break
            else:
                raise KeyError(
                    f"Widget identifier '{filt_plot_id}' not found!")
            return wi
        elif slot_id is not None and filt_plot_id is not None:
            # get a matrix element
            wd = self.ui.data_matrix.element_widget_dict
            wp = self.ui.plot_matrix.element_widget_dict
            fpd = wd[slot_id]
            fpp = wp[slot_id]
            if filt_plot_id in fpp:
                wi = fpp[filt_plot_id]
            elif filt_plot_id in fpd:
                wi = fpd[filt_plot_id]
            else:
                raise KeyError(
                    f"Widget identifier '{filt_plot_id}' not found!")
            return wi
        else:
            raise ValueError(
                "At least one of `slot_id`, `filt_plot_id` must be specified!")

    def update(self, *args, **kwargs):
        self.ui.scrollArea_block.update()
        super().update(*args, **kwargs)
