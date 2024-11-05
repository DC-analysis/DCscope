import copy

import numpy as np
from PyQt6 import QtCore, QtWidgets

from ... import pipeline

from .dm_dataset import MatrixDataset
from .dm_filter import MatrixFilter
from .dm_element import MatrixElement


class DataMatrix(QtWidgets.QWidget):
    quickviewed = QtCore.pyqtSignal(int, int)
    matrix_changed = QtCore.pyqtSignal()
    filter_modify_clicked = QtCore.pyqtSignal(str)
    slot_modify_clicked = QtCore.pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super(DataMatrix, self).__init__(*args, **kwargs)

        self.glo = None
        self._reset_layout()

        self.setAcceptDrops(True)

        # used for toggling between all active, all inactive and semi state
        self.semi_states_dataset = {}
        self.semi_states_filter = {}

        # used for remembering quickview element
        self._old_quickview_instance = None

    def __getstate__(self):
        """State of the current data matrix"""
        # slots
        slot_states = []
        slots_used = []
        for dw in self.dataset_widgets:
            dw_state = dw.__getstate__()
            slot = pipeline.Dataslot.get_slot(dw_state["identifier"])
            slot.slot_used = dw_state["enabled"]
            slot_states.append(slot.__getstate__())
            if dw_state["enabled"]:
                slots_used.append(dw_state["identifier"])

        # filters
        filter_states = []
        filters_used = []
        for fw in self.filter_widgets:
            fw_state = fw.__getstate__()
            filt = pipeline.Filter.get_filter(fw_state["identifier"])
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
                idict[fw.identifier] = me.__getstate__()["active"]
            mestates[dw.identifier] = idict
        state = {"elements": mestates,
                 "filters": filter_states,
                 "filters used": filters_used,
                 "slots": slot_states,
                 "slots used": slots_used,
                 }
        return state

    def __setstate__(self, state):
        # remember current QuickView identifiers
        qv_slot_id, qv_filt_id = self.get_quickview_ids()
        self.blockSignals(True)
        self.clear()
        # dataset states
        for ii in range(len(state["slots"])):
            slot_id = state["slots"][ii]["identifier"]
            dw_state = {"path": state["slots"][ii]["path"],
                        "identifier": slot_id,
                        "enabled": slot_id in state["slots used"],
                        }
            self.add_dataset(state=dw_state)
        # filter states
        for jj in range(len(state["filters"])):
            filt_id = state["filters"][jj]["identifier"]
            fw_state = {"identifier": filt_id,
                        "enabled": filt_id in state["filters used"],
                        "name": state["filters"][jj]["name"]
                        }
            self.add_filter(state=fw_state)
        # make sure elements exist
        # (this also sets enabled/disabled state)
        self.fill_elements()
        # element states
        MatrixElement._quick_view_instance = None
        for slot_id in state["elements"]:
            ds_state = state["elements"][slot_id]
            for filt_id in ds_state:
                me = self.get_matrix_element(slot_id, filt_id)
                me_state = me.__getstate__()
                me_state["active"] = ds_state[filt_id]
                me.__setstate__(me_state)
        # re-apply current quickview ids
        try:
            meqv = self.get_matrix_element(qv_slot_id, qv_filt_id)
        except KeyError:
            pass
        else:
            MatrixElement._quick_view_instance = meqv
            self.update_content()
        self.blockSignals(False)

    def _reset_layout(self):
        if self.glo is not None:
            # send old layout to Nirvana eventually
            layout = self.glo
            self.glo = None
            self.old_layout = QtWidgets.QWidget()
            self.old_layout.setLayout(layout)
            self.old_layout.hide()
            self.old_layout.deleteLater()
        # add new layout
        self.glo = QtWidgets.QGridLayout()
        self.glo.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.glo.setSpacing(2)
        self.glo.setContentsMargins(0, 0, 0, 0)
        # add dummy corner element
        cl = QtWidgets.QLabel("Block\nMatrix")
        cl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.glo.addWidget(cl, 0, 0)
        self.setLayout(self.glo)

    @property
    def dataset_widgets(self):
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
        filters = []
        for jj in range(self.glo.columnCount()):
            item = self.glo.itemAtPosition(0, jj+1)
            if item is not None:
                fs = item.widget()
                filters.append(fs)
        return filters

    @property
    def num_datasets(self):
        count = 0
        for ii in range(1, self.glo.rowCount()):
            if self.glo.itemAtPosition(ii, 0) is not None:
                count += 1
        return count

    @property
    def num_filters(self):
        count = 0
        for jj in range(1, self.glo.columnCount()):
            if self.glo.itemAtPosition(0, jj) is not None:
                count += 1
        return count

    @property
    def plot_matrix(self):
        for ch in self.parent().children():
            if ch.__class__.__name__ == "PlotMatrix":
                break
        else:
            raise KeyError("PlotMatrix not found!")
        return ch

    def add_dataset(self, slot_id=None, state=None):
        """Add a dataset to the DataMatrix"""
        md = MatrixDataset(identifier=slot_id, state=state)
        self.glo.addWidget(md, self.num_datasets+1, 0)
        md.active_toggled.connect(self.toggle_dataset_active)
        md.enabled_toggled.connect(self.toggle_dataset_enable)
        md.enabled_toggled.connect(self.plot_matrix.toggle_dataset_enable)
        md.option_action.connect(self.on_option_dataset)
        md.modify_clicked.connect(self.slot_modify_clicked.emit)
        self.fill_elements()
        self.plot_matrix.fill_elements()
        self.adjust_size()
        self.plot_matrix.adjust_size()  # important when opt/removing slots
        self.publish_matrix()
        return md

    def add_filter(self, identifier=None, state=None):
        mf = MatrixFilter(identifier=identifier, state=state)
        mf.active_toggled.connect(self.toggle_filter_active)
        mf.enabled_toggled.connect(self.toggle_filter_enable)
        mf.option_action.connect(self.on_option_filter)
        mf.modify_clicked.connect(self.filter_modify_clicked.emit)
        self.glo.addWidget(mf, 0, self.num_filters+1)
        self.fill_elements()
        self.adjust_size()
        self.plot_matrix.adjust_size()  # important when opt/removing filters
        self.publish_matrix()
        return mf

    def adjust_size(self):
        QtWidgets.QApplication.processEvents(
            QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
        self.setMinimumSize(self.sizeHint())
        self.setFixedSize(self.sizeHint())
        QtWidgets.QApplication.processEvents(
            QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
        self.setMinimumSize(self.sizeHint())
        self.setFixedSize(self.sizeHint())

    def changed_element(self):
        self.publish_matrix()

    def changed_quickview(self):
        slot_index_qv, filt_index_qv = self.get_quickview_indices()
        if slot_index_qv is not None and filt_index_qv is not None:
            self.quickviewed.emit(slot_index_qv, filt_index_qv)

    def enable_quickview(self, b=True):
        if b:
            MatrixElement._quick_view_instance = self._old_quickview_instance
        else:
            self._old_quickview_instance = MatrixElement._quick_view_instance
            MatrixElement._quick_view_instance = None
        self.update_content()

    def clear(self):
        """Reset layout"""
        self._reset_layout()

    def dragEnterEvent(self, event):
        # drag enter event on data matrix
        event.ignore()

    def dropEvent(self, event):
        # drag drop event on data matrix
        event.ignore()

    def fill_elements(self):
        # add widgets
        for ii in range(self.num_datasets):
            for jj in range(self.num_filters):
                if self.glo.itemAtPosition(ii+1, jj+1) is None:
                    me = MatrixElement()
                    me.quickview_selected.connect(self.changed_quickview)
                    me.element_changed.connect(self.changed_element)
                    self.glo.addWidget(me, ii+1, jj+1)
        # make sure enabled/disabled is honored
        state = self.__getstate__()
        for slot_sate in state["slots"]:
            slot_id = slot_sate["identifier"]
            for filt_state in state["filters"]:
                filt_id = filt_state["identifier"]
                if not (slot_id in state["slots used"]
                        and filt_id in state["filters used"]):
                    me = self.get_matrix_element(slot_id, filt_id)
                    mstate = me.__getstate__()
                    mstate["enabled"] = False
                    me.__setstate__(mstate)

    def get_filter_index(self, filter_id):
        for ii, fs in enumerate(self.filter_widgets):
            if fs.identifier == filter_id:
                break
        else:
            raise KeyError("Filter '{}' not found!".format(filter_id))
        return ii

    def get_filter_widget_state(self, filter_id):
        ii = self.get_filter_index(filter_id)
        fw = self.filter_widgets[ii]
        return fw.__getstate__()

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
            return dw.__getstate__(), ii
        else:
            return dw.__getstate__()

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

    def get_quickview_ids(self):
        current = MatrixElement._quick_view_instance
        if current is not None:
            try:
                state = self.__getstate__()
            except KeyError:
                # the state is not valid (issue #25)
                return None, None
            for slot_id in state["elements"]:
                ds_state = state["elements"][slot_id]
                for filt_id in ds_state:
                    me = self.get_matrix_element(slot_id, filt_id)
                    if current == me:
                        return slot_id, filt_id
            else:
                # no valid QuickView selection (issue #38)
                return None, None
        else:
            return None, None

    def get_quickview_indices(self):
        slot_id, filt_id = self.get_quickview_ids()
        if slot_id is not None:
            ii, jj = self.get_matrix_indices(slot_id, filt_id)
            return ii - 1, jj - 1
        else:
            return None, None

    @QtCore.pyqtSlot(str)
    def on_option_dataset(self, option):
        """Dataset option logic (remove, insert_anew, duplicate)"""
        dw_state = self.sender().__getstate__()
        slot_id = dw_state["identifier"]
        slot_index = self.get_slot_index(slot_id)
        state = self.__getstate__()
        pstate = self.plot_matrix.__getstate__()
        if option == "remove":
            state["slots"].pop(slot_index)
            if slot_id in state["slots used"]:
                state["slots used"].remove(slot_id)
            state["elements"].pop(slot_id)
            pstate["elements"].pop(slot_id)
        else:
            # create a new slot
            slot = pipeline.Dataslot(path=dw_state["path"])
            new_id = slot.identifier
            if option == "duplicate":
                # use original state
                new_state = copy.deepcopy(state["slots"][slot_index])
                # only set the new identifier (issue #96)
                new_state["identifier"] = new_id
            else:  # insert_anew
                new_state = slot.__getstate__()
            slot.__setstate__(new_state)
            state["slots"].insert(slot_index+1, new_state)
            state["slots used"].append(new_id)
        # this also takes care of filling up matrix elements
        self.__setstate__(state)
        # this correctly assigns elements in plot matrix
        # (also when option is not remove)
        self.plot_matrix.__setstate__(pstate)
        self.plot_matrix.fill_elements()
        self.publish_matrix()

    @QtCore.pyqtSlot(str)
    def on_option_filter(self, option):
        """Filter option logic (remove, duplicate)"""
        fw_state = self.sender().__getstate__()
        filt_id = fw_state["identifier"]
        filt_index = self.get_filter_index(filt_id)
        state = self.__getstate__()
        if option == "remove":
            state["filters"].pop(filt_index)
            # remove matrix elements
            for ds_key in state["elements"]:
                state["elements"][ds_key].pop(filt_id)
        else:  # duplicate
            filt = pipeline.Filter()
            new_state = copy.deepcopy(state["filters"][filt_index])
            new_state["identifier"] = filt.identifier
            new_state["name"] = filt.name
            state["filters"].insert(filt_index+1, new_state)
            state["filters used"].append(filt.identifier)
            filt.__setstate__(new_state)
        self.__setstate__(state)
        self.publish_matrix()

    def publish_matrix(self):
        """Publish state via self.matrix_changed signal for Pipeline"""
        if not self.signalsBlocked():
            self.matrix_changed.emit()
            self.changed_quickview()

    @QtCore.pyqtSlot()
    def toggle_dataset_active(self):
        """Switch between all active, all inactive, previous state

        Modifies the matrix elements for a dataset/row,
        which is defined by the signal sender :class:`MatrixDataset`.
        Cyclic toggling order: semi -> all -> none
        """
        self.semi_states_filter = {}  # sic
        sender = self.sender()
        slot_id = sender.identifier
        state = self.__getstate__()["elements"][slot_id]
        num_actives = sum([s for s in state.values()])

        # update state according to the scheme in the docstring
        if num_actives == 0:
            if slot_id in self.semi_states_dataset:
                # use semi state
                oldstate = self.semi_states_dataset[slot_id]
                for filt_id in oldstate:
                    if filt_id in state:
                        state[filt_id] = oldstate[filt_id]
            else:
                # toggle all to active
                for filt_id in state:
                    state[filt_id] = True
        elif num_actives == len(state):
            # toggle all to inactive
            for filt_id in state:
                state[filt_id] = False
        else:
            # save semi state
            self.semi_states_dataset[slot_id] = copy.deepcopy(state)
            # toggle all to active
            for filt_id in state:
                state[filt_id] = True

        for filt_id in state:
            me = self.get_matrix_element(slot_id, filt_id)
            me.set_active(state[filt_id])
        self.publish_matrix()

    @QtCore.pyqtSlot(bool)
    def toggle_dataset_enable(self, enabled):
        sender = self.sender()
        slot_id = sender.identifier
        state = self.__getstate__()
        for filt_id in state["elements"][slot_id]:
            # make sure that disabled filters are honored
            fstate = self.get_filter_widget_state(filt_id)
            fenabled = fstate["enabled"]
            # update element widget
            me = self.get_matrix_element(slot_id, filt_id)
            mstate = me.__getstate__()
            mstate["enabled"] = np.logical_and(enabled, fenabled)
            me.__setstate__(mstate)
        self.publish_matrix()

    @QtCore.pyqtSlot()
    def toggle_filter_active(self):
        """Switch between all active, all inactive, previous state

        Modifies the matrix elements for a filter/column,
        which is defined by the signal sender :class:`MatrixFilter`.
        Cyclic toggling order: semi -> all -> none
        """
        self.semi_states_dataset = {}  # sic
        sender = self.sender()
        filt_id = sender.identifier

        states = self.__getstate__()["elements"]
        state = {}
        for slot_id in states:
            state[slot_id] = states[slot_id][filt_id]

        num_actives = sum(list(state.values()))

        # update state according to the scheme in the docstring
        if num_actives == 0:
            if filt_id in self.semi_states_filter:
                # use semi state
                oldstate = self.semi_states_filter[filt_id]
                for slot_id in oldstate:
                    if slot_id in state:
                        state[slot_id] = oldstate[slot_id]
            else:
                # toggle all to active
                for slot_id in state:
                    state[slot_id] = True
        elif num_actives == len(state):
            # toggle all to inactive
            for slot_id in state:
                state[slot_id] = False
        else:
            # save semi state
            self.semi_states_filter[filt_id] = copy.deepcopy(state)
            # toggle all to active
            for slot_id in state:
                state[slot_id] = True

        for slot_id in state:
            me = self.get_matrix_element(slot_id, filt_id)
            me.set_active(state[slot_id])
        self.publish_matrix()

    @QtCore.pyqtSlot(bool)
    def toggle_filter_enable(self, enabled):
        sender = self.sender()
        sid = sender.identifier
        state = self.__getstate__()
        for slot_id in state["elements"]:
            # make sure that disabled filters are honored
            dstate = self.get_slot_widget_state(slot_id)
            denabled = dstate["enabled"]
            # update element widget
            me = self.get_matrix_element(slot_id, sid)
            mstate = me.__getstate__()
            mstate["enabled"] = np.logical_and(enabled, denabled)
            me.__setstate__(mstate)
        self.publish_matrix()

    def update_content(self):
        ncols = self.glo.columnCount()
        nrows = self.glo.rowCount()
        for ii in range(nrows):
            for jj in range(ncols):
                if ii == 0 and jj == 0:
                    # block matrix label
                    continue
                item = self.glo.itemAtPosition(ii, jj)
                if item is not None:
                    item.widget().update_content()
