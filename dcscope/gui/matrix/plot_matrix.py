from PyQt6 import QtCore, QtWidgets

from .pm_element import PlotMatrixElement
from .pm_plot import MatrixPlot


class PlotMatrix(QtWidgets.QWidget):
    plot_modify_clicked = QtCore.pyqtSignal(str)

    # widgets emit these whenever they changed the pipeline
    pp_mod_send = QtCore.pyqtSignal(dict)
    # widgets receive these so they can reflect the pipeline changes
    pp_mod_recv = QtCore.pyqtSignal(dict)
    # child widgets receive this after pp_mod_recv is received
    pp_mod_recv_child = QtCore.pyqtSignal(dict)

    def __init__(self, *args, **kwargs):
        super(PlotMatrix, self).__init__(*args, **kwargs)

        self.pipeline = None

        # add grid layout
        self.glo = QtWidgets.QGridLayout()
        self.glo.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.glo.setSpacing(2)
        self.glo.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.glo)

        self.setMouseTracking(True)

        self.pp_mod_recv.connect(self.on_pp_mod_recv)

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

    # properties
    @property
    def data_matrix(self):
        for ch in self.parent().children():
            if ch.__class__.__name__ == "DataMatrix":
                break
        else:
            raise KeyError("DataMatrix not found!")
        return ch

    @property
    def element_widget_dict(self):
        """Dictionary of all widgets in the plot matrix, keys are indices"""
        els = {}
        for ii, slot_id in enumerate(self.pipeline.slot_ids):
            elsd = {}
            for jj, plot_id in enumerate(self.pipeline.plot_ids):
                it = self.glo.itemAtPosition(ii+1, jj)
                elsd[plot_id] = it.widget()
            els[slot_id] = elsd
        return els

    # other methods
    def fill_matrix(self):
        # add widgets
        for ii in range(self.pipeline.num_slots):
            # plot matrix element row
            erow = ii + 1

            for jj in range(self.pipeline.num_plots):
                # plot matrix element column
                ecol = jj

                if self.glo.itemAtPosition(0, ecol) is None:
                    # first row contains plot information
                    pm = MatrixPlot(parent=self,
                                    pipeline=self.pipeline,
                                    plot_index=jj)
                    self.glo.addWidget(pm, 0, ecol)
                    self.pp_mod_recv_child.connect(pm.pp_mod_recv)
                    pm.modify_clicked.connect(self.plot_modify_clicked.emit)
                    pm.pp_mod_send.connect(self.pp_mod_send)

                if self.glo.itemAtPosition(erow, ecol) is None:
                    # These are data matrix elements
                    me = PlotMatrixElement(parent=self,
                                           pipeline=self.pipeline,
                                           slot_index=ii,
                                           plot_index=jj)
                    self.glo.addWidget(me, erow, ecol)
                    self.pp_mod_recv_child.connect(me.pp_mod_recv)
                    me.pp_mod_send.connect(self.pp_mod_send)

        # remove rows
        for ii in range(self.pipeline.num_slots + 1, self.glo.rowCount()):
            for jj in range(0, self.glo.columnCount()):
                item = self.glo.itemAtPosition(ii, jj)
                if item is not None:
                    item.widget().abolish()
                    self.glo.removeItem(item)

        # remove columns
        for jj in range(self.pipeline.num_plots, self.glo.columnCount()):
            for ii in range(0, self.glo.rowCount()):
                item = self.glo.itemAtPosition(ii, jj)
                if item is not None:
                    item.widget().abolish()
                    self.glo.removeItem(item)

        # adjust size
        ncols = self.pipeline.num_plots
        nrows = self.pipeline.num_slots + 1
        if ncols and nrows:
            width1 = self.glo.itemAt(0).widget().width()
            width = (width1 + 2)*ncols - 2
            height = self.data_matrix.sizeHint().height()
            self.setMinimumSize(width, height)
            self.setFixedSize(width, height)
            QtWidgets.QApplication.processEvents(
                QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
            self.setMinimumSize(width, height)
            self.setFixedSize(width, height)
        else:
            self.setFixedSize(65, 50)

        self.update()

    @QtCore.pyqtSlot(dict)
    def on_pp_mod_recv(self, data):
        """We received a signal that something changed"""
        if data.get("pipeline"):
            # Something in the pipeline changed. Make sure that we have
            # enough columns and rows.
            self.fill_matrix()
            # let all child widgets know the change
            self.pp_mod_recv_child.emit(data)

    # Other methods
    @property
    def plot_widgets(self):
        plots = []
        for jj in range(self.glo.columnCount()):
            item = self.glo.itemAtPosition(0, jj)
            if item is not None:
                ps = item.widget()
                plots.append(ps)
        return plots

    def get_plot_index(self, plot_id):
        for ii, pw in enumerate(self.plot_widgets):
            if pw.identifier == plot_id:
                break
        else:
            raise KeyError("Dataset '{}' not found!".format(plot_id))
        return ii

    def get_plot_widget_state(self, plot_id, ret_index=False):
        ii = self.get_plot_index(plot_id)
        pw = self.plot_widgets[ii]
        if ret_index:
            return pw.read_pipeline_state(), ii
        else:
            return pw.read_pipeline_state()

    def set_pipeline(self, pipeline):
        if self.pipeline is not None:
            raise ValueError("Pipeline can only be set once")
        self.pipeline = pipeline
