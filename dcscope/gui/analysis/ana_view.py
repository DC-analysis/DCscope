from PyQt6 import QtCore, QtWidgets

from ..helpers import connect_pp_mod_signals
from .ana_view_ui import Ui_Form


class AnalysisView(QtWidgets.QWidget):
    # widgets emit these whenever they changed the pipeline
    pp_mod_send = QtCore.pyqtSignal(dict)
    # widgets receive these so they can reflect the pipeline changes
    pp_mod_recv = QtCore.pyqtSignal(dict)

    def __init__(self, *args, **kwargs):
        super(AnalysisView, self).__init__(*args, **kwargs)

        self.ui = Ui_Form()
        self.ui.setupUi(self)

        self._quickview_slot_index = 0
        self._quickview_filt_index = 0

        self.page_widgets = [
            self.ui.widget_basins,
            self.ui.widget_meta,
            self.ui.widget_filter,
            self.ui.widget_log,
            self.ui.widget_plot,
            self.ui.widget_slot,
            self.ui.widget_tables
        ]

        self.setWindowTitle("Analysis View")
        self.setMinimumSize(self.sizeHint())
        # Signals
        self.ui.tabWidget.setCurrentIndex(0)
        self.ui.tabWidget.currentChanged.connect(self.update_content)

        for pw in self.page_widgets:
            connect_pp_mod_signals(self, pw)

    @QtCore.pyqtSlot(bool)
    def on_visible(self, visible):
        if visible:
            self.update_content()

    def set_pipeline(self, pipeline):
        self._quickview_filt_index = min(self._quickview_filt_index,
                                         len(pipeline.filters) - 1)
        self._quickview_slot_index = min(self._quickview_slot_index,
                                         len(pipeline.slots) - 1)

        for widget in self.page_widgets:
            widget.set_pipeline(pipeline)

        self.update_content()

    @QtCore.pyqtSlot()
    def update_content(self):
        cur_page = self.ui.tabWidget.currentWidget()
        for widget in self.page_widgets:
            if widget.parent() is cur_page:
                widget.update_content(
                    slot_index=self._quickview_slot_index,
                    filt_index=self._quickview_filt_index)
                break
