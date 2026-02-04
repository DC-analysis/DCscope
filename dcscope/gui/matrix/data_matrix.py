from PyQt6 import QtCore, QtWidgets

from .dm_dataset import MatrixDataset
from .dm_filter import MatrixFilter
from .dm_element import DataMatrixElement


class DataMatrix(QtWidgets.QWidget):
    filter_modify_clicked = QtCore.pyqtSignal(str)
    slot_modify_clicked = QtCore.pyqtSignal(str)

    # widgets emit these whenever they changed the pipeline
    pp_mod_send = QtCore.pyqtSignal(dict)
    # widgets receive these so they can reflect the pipeline changes
    pp_mod_recv = QtCore.pyqtSignal(dict)
    # child widgets receive this after pp_mod_recv is received
    pp_mod_recv_child = QtCore.pyqtSignal(dict)

    def __init__(self, *args, **kwargs):
        super(DataMatrix, self).__init__(*args, **kwargs)

        self.pipeline = None

        # add grid layout
        self.glo = QtWidgets.QGridLayout()
        self.glo.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.glo.setSpacing(2)
        self.glo.setContentsMargins(0, 0, 0, 0)
        # add dummy corner element
        cl = QtWidgets.QLabel("Block\nMatrix")
        cl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.glo.addWidget(cl, 0, 0)
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

    def fill_matrix(self):
        # filters (column headers)
        for jj in range(self.pipeline.num_filters):
            # data matrix element column
            ecol = jj + 1
            if self.glo.itemAtPosition(0, ecol) is None:
                # first row contains filter information
                fm = MatrixFilter(parent=self,
                                  pipeline=self.pipeline,
                                  filt_index=jj)
                self.glo.addWidget(fm, 0, ecol)
                self.pp_mod_recv_child.connect(fm.pp_mod_recv)
                fm.modify_clicked.connect(self.filter_modify_clicked.emit)
                fm.pp_mod_send.connect(self.pp_mod_send)

        # slots (row headers) and matrix elements
        for ii in range(self.pipeline.num_slots):
            # data matrix row
            erow = ii + 1
            if self.glo.itemAtPosition(erow, 0) is None:
                # first column contains slot information
                dm = MatrixDataset(parent=self,
                                   pipeline=self.pipeline,
                                   slot_index=ii,
                                   )
                self.glo.addWidget(dm, erow, 0)
                self.pp_mod_recv_child.connect(dm.pp_mod_recv)
                dm.modify_clicked.connect(self.slot_modify_clicked.emit)
                dm.pp_mod_send.connect(self.pp_mod_send)

            for jj in range(self.pipeline.num_filters):
                ecol = jj + 1
                if self.glo.itemAtPosition(erow, ecol) is None:
                    # These are data matrix elements
                    me = DataMatrixElement(parent=self,
                                           pipeline=self.pipeline,
                                           slot_index=ii,
                                           filt_index=jj)
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
        for jj in range(self.pipeline.num_filters + 1, self.glo.columnCount()):
            for ii in range(0, self.glo.rowCount()):
                item = self.glo.itemAtPosition(ii, jj)
                if item is not None:
                    item.widget().abolish()
                    self.glo.removeItem(item)

        # adjust size
        QtWidgets.QApplication.processEvents(
            QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
        self.setMinimumSize(self.sizeHint())
        self.setFixedSize(self.sizeHint())
        QtWidgets.QApplication.processEvents(
            QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
        self.setMinimumSize(self.sizeHint())
        self.setFixedSize(self.sizeHint())

        self.update()

    @QtCore.pyqtSlot(dict)
    def on_pp_mod_recv(self, data):
        """We received a signal that something changed"""
        if (data.get("pipeline")
            or data.get("quickview")
                or data.get("block_matrix")):
            # Something in the pipeline changed. Make sure that we have
            # enough columns and rows.
            self.fill_matrix()
            # let all child widgets know the change
            self.pp_mod_recv_child.emit(data)

    def read_pipeline_state(self):
        """State of the current data matrix"""
        # slots
        slot_states = []
        slots_used = []
        for dw in self.dataset_widgets:
            dw_state = dw.read_pipeline_state()
            slot = self.pipeline.get_slot(dw_state["identifier"])
            slot.slot_used = dw_state["enabled"]
            slot_states.append(slot.__getstate__())
            if dw_state["enabled"]:
                slots_used.append(dw_state["identifier"])

        # filters
        filter_states = []
        filters_used = []
        for fw in self.filter_widgets:
            fw_state = fw.read_pipeline_state()
            filt = self.pipeline.get_filter(fw_state["identifier"])
            filter_states.append(filt.__getstate__())
            if fw_state["enabled"]:
                filters_used.append(fw_state["identifier"])
        # elements
        mestates = {}
        for dw in self.dataset_widgets:
            idict = {}
            for fw in self.filter_widgets:
                me = self.get_matrix_element(dw.identifier, fw.identifier)
                # We only store the information about whether the user
                # clicked this element. The state about "enabled" is stored
                # in `slots_used` and `filters_used`.
                idict[fw.identifier] = me.read_pipeline_state()["active"]
            mestates[dw.identifier] = idict
        state = {"elements": mestates,
                 "filters": filter_states,
                 "filters used": filters_used,
                 "slots": slot_states,
                 "slots used": slots_used,
                 }
        return state

    @property
    def dataset_widgets(self):
        """Return list of `MatrixDataset`"""
        datasets = []
        for ii in range(self.glo.rowCount()):
            item = self.glo.itemAtPosition(ii+1, 0)
            if item is not None:
                ds = item.widget()
                datasets.append(ds)
        return datasets

    @property
    def element_width(self):
        """Data matrix element width (without 2px spacing)"""
        for jj in range(1, self.glo.columnCount()-1):
            item = self.glo.itemAtPosition(0, jj)
            if item is not None:
                width = item.geometry().width()
                break
        else:
            width = 67
        return width

    @property
    def element_widget_dict(self):
        """Dictionary of all widgets in the data matrix, keys are indices"""
        els = {}
        for ii, ws in enumerate(self.dataset_widgets):
            elsd = {}
            for jj, wf in enumerate(self.filter_widgets):
                it = self.glo.itemAtPosition(ii+1, jj+1)
                elsd[wf.identifier] = it.widget()
            els[ws.identifier] = elsd
        return els

    @property
    def filter_widgets(self):
        """List of `MatrixFilter` instances"""
        filters = []
        for jj in range(self.glo.columnCount()):
            item = self.glo.itemAtPosition(0, jj+1)
            if item is not None:
                fs = item.widget()
                filters.append(fs)
        return filters

    def get_filt_index(self, filter_id):
        for ii, fs in enumerate(self.filter_widgets):
            if fs.identifier == filter_id:
                break
        else:
            raise KeyError("Filter '{}' not found!".format(filter_id))
        return ii

    def get_filter_widget_state(self, filter_id):
        ii = self.get_filt_index(filter_id)
        fw = self.filter_widgets[ii]
        return fw.read_pipeline_state()

    def get_slot_index(self, slot_id):
        for ii, dw in enumerate(self.dataset_widgets):
            if dw.identifier == slot_id:
                break
        else:
            raise KeyError("Dataset '{}' not found!".format(slot_id))
        return ii

    def get_slot_widget_state(self, slot_id, ret_index=False):
        ii = self.get_slot_index(slot_id)
        dw = self.dataset_widgets[ii]
        if ret_index:
            return dw.read_pipeline_state(), ii
        else:
            return dw.read_pipeline_state()

    def get_matrix_element(self, slot_id, filt_id):
        """Return matrix element matching dataset and filter identifiers"""
        ii, jj = self.get_matrix_indices(slot_id, filt_id)
        return self.glo.itemAtPosition(ii, jj).widget()

    def get_matrix_indices(self, slot_id, filt_id):
        ncols = self.glo.columnCount()
        nrows = self.glo.rowCount()
        for ii in range(1, nrows):
            ds = self.glo.itemAtPosition(ii, 0).widget()
            if ds.identifier == slot_id:
                for jj in range(1, ncols):
                    f = self.glo.itemAtPosition(0, jj).widget()
                    if f.identifier == filt_id:
                        break
                else:
                    raise KeyError("Filter '{}' not found!".format(filt_id))
                break
        else:
            raise KeyError("Dataset '{}' not found!".format(slot_id))
        return ii, jj

    def set_pipeline(self, pipeline):
        if self.pipeline is not None:
            raise ValueError("Pipeline can only be set once")
        self.pipeline = pipeline
