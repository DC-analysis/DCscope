import copy

from PyQt6 import QtCore, QtWidgets

from ... import pipeline

from .pm_element import MatrixElement
from .pm_plot import MatrixPlot


class PlotMatrix(QtWidgets.QWidget):
    plot_modify_clicked = QtCore.pyqtSignal(str)
    matrix_changed = QtCore.pyqtSignal()

    def __init__(self, *args, **kwargs):
        super(PlotMatrix, self).__init__(*args, **kwargs)

        self.glo = None
        self._reset_layout(init=True)

        # used for toggling between all active, all inactive and semi state
        self.semi_states_plot = {}

    def __getstate__(self):
        """State of the current plot matrix"""
        # plots
        plots = []
        for pw in self.plot_widgets:
            pw_state = pw.__getstate__()
            plot = pipeline.Plot._instances[pw_state["identifier"]]
            plots.append(plot.__getstate__())
        # elements
        mestates = {}
        dm = self.data_matrix
        for dw in dm.dataset_widgets:
            idict = {}
            for pw in self.plot_widgets:
                me = self.get_matrix_element(dw.identifier, pw.identifier)
                idict[pw.identifier] = me.__getstate__()["active"]
            mestates[dw.identifier] = idict
        state = {"elements": mestates,
                 "plots": plots}
        return state

    def __setstate__(self, state):
        self.setUpdatesEnabled(False)
        self.blockSignals(True)
        self.clear()
        # plot states
        for jj in range(len(state["plots"])):
            plot_id = state["plots"][jj]["identifier"]
            pw_state = {"identifier": plot_id,
                        "name": state["plots"][jj]["layout"]["name"],
                        }
            self.add_plot(state=pw_state)
        # make sure elements exist
        self.fill_elements()
        # element states
        for slot_id in state["elements"]:
            ds_d = state["elements"][slot_id]
            for plot_id in ds_d:
                el = self.get_matrix_element(slot_id, plot_id)
                el_state = el.__getstate__()
                el_state["active"] = ds_d[plot_id]
                el.__setstate__(el_state)
        self.blockSignals(False)
        self.setUpdatesEnabled(True)

    def _reset_layout(self, init=False):
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
        self.glo.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.glo.setSpacing(2)
        self.glo.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.glo)

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
        els = {}
        for ii, ws in enumerate(self.data_matrix.dataset_widgets):
            elsd = {}
            for jj, wf in enumerate(self.plot_widgets):
                it = self.glo.itemAtPosition(ii+1, jj)
                elsd[wf.identifier] = it.widget()
            els[ws.identifier] = elsd
        return els

    @property
    def element_width(self):
        """Data matrix element width (without 2px spacing)"""
        return self.data_matrix.element_width

    @property
    def num_datasets(self):
        dm = self.data_matrix
        return dm.num_datasets

    @property
    def num_plots(self):
        count = 0
        for jj in range(self.glo.columnCount()):
            if self.glo.itemAtPosition(0, jj) is not None:
                count += 1
        return count

    @property
    def plot_widgets(self):
        plots = []
        for jj in range(self.glo.columnCount()):
            item = self.glo.itemAtPosition(0, jj)
            if item is not None:
                ps = item.widget()
                plots.append(ps)
        return plots

    def add_plot(self, identifier=None, state=None):
        self.setUpdatesEnabled(False)
        mp = MatrixPlot(identifier=identifier, state=state)
        mp.option_action.connect(self.on_option_plot)
        mp.active_toggled.connect(self.toggle_plot_active)
        mp.modify_clicked.connect(self.plot_modify_clicked.emit)
        self.glo.addWidget(mp, 0, self.num_plots)
        self.fill_elements()
        self.adjust_size()
        self.setUpdatesEnabled(True)
        self.publish_matrix()
        return mp

    def adjust_size(self):
        ncols = self.num_plots
        nrows = self.data_matrix.num_datasets
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

    @QtCore.pyqtSlot()
    def changed_element(self):
        self.publish_matrix()

    def clear(self):
        """Reset layout"""
        self._reset_layout()
        self.semi_states_plot = {}

    def fill_elements(self):
        # add widgets
        for ii in range(self.num_datasets):
            for jj in range(self.num_plots):
                if self.glo.itemAtPosition(ii+1, jj) is None:
                    me = MatrixElement()
                    me.element_changed.connect(self.changed_element)
                    self.glo.addWidget(me, ii+1, jj)
        # make sure enabled/disabled is honored
        dstate = self.data_matrix.__getstate__()
        pstate = self.__getstate__()
        for slot_state in dstate["slots"]:
            slot_id = slot_state["identifier"]
            if slot_id not in dstate["slots used"]:
                for plot_state in pstate["plots"]:
                    plot_id = plot_state["identifier"]
                    me = self.get_matrix_element(slot_id, plot_id)
                    mstate = me.__getstate__()
                    mstate["enabled"] = False
                    me.__setstate__(mstate)

    def get_matrix_element(self, dataset_id, plot_id):
        """Return matrix element matching dataset and plot identifiers"""
        ncols = self.glo.columnCount()
        nrows = self.glo.rowCount()
        for ii in range(1, nrows):
            dw = self.data_matrix.glo.itemAtPosition(ii, 0).widget()
            if dw.identifier == dataset_id:
                for jj in range(ncols):
                    f = self.glo.itemAtPosition(0, jj).widget()
                    if f.identifier == plot_id:
                        break
                else:
                    raise KeyError("Plot '{}' not found!".format(plot_id))
                break
        else:
            raise KeyError("Dataset '{}' not found!".format(dataset_id))
        return self.glo.itemAtPosition(ii, jj).widget()

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
            return pw.__getstate__(), ii
        else:
            return pw.__getstate__()

    @QtCore.pyqtSlot(str)
    def on_option_plot(self, option):
        """Plot option logic (remove, duplicate)"""
        pw_state = self.sender().__getstate__()
        plot_id = pw_state["identifier"]
        plot_index = self.get_plot_index(plot_id)
        state = self.__getstate__()
        if option == "remove":
            state["plots"].pop(plot_index)
            for ds_key in state["elements"]:
                state["elements"][ds_key].pop(plot_id)
        else:  # duplicate
            plot = pipeline.Plot()
            new_state = copy.deepcopy(state["plots"][plot_index])
            new_state["identifier"] = plot.identifier
            new_state["layout"]["name"] = plot.name
            state["plots"].insert(plot_index+1, new_state)
            plot.__setstate__(new_state)
        self.__setstate__(state)
        self.publish_matrix()

    def publish_matrix(self):
        """Publish state via self.matrix_changed signal for Pipeline"""
        if not self.signalsBlocked():
            self.matrix_changed.emit()

    @QtCore.pyqtSlot(bool)
    def toggle_dataset_enable(self, enabled):
        sender = self.sender()
        sid = sender.identifier
        state = self.__getstate__()
        for p_key in state["elements"][sid]:
            # update element widget
            me = self.get_matrix_element(sid, p_key)
            mstate = me.__getstate__()
            mstate["enabled"] = enabled
            me.__setstate__(mstate)
        self.publish_matrix()

    @QtCore.pyqtSlot()
    def toggle_plot_active(self):
        """Switch between all active, all inactive, previous state

        Modifies the matrix elements for a plot/column,
        which is defined by the signal sender :class:`MatrixPlot`.
        Cyclic toggling order: semi -> all -> none
        """
        sender = self.sender()
        plot_id = sender.identifier

        states = self.__getstate__()["elements"]
        state = {}
        for slot_id in states:
            state[slot_id] = states[slot_id][plot_id]

        num_actives = sum(list(state.values()))

        # update state according to the scheme in the docstring
        if num_actives == 0:
            if plot_id in self.semi_states_plot:
                # use semi state
                oldstate = self.semi_states_plot[plot_id]
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
            self.semi_states_plot[plot_id] = copy.deepcopy(state)
            # toggle all to active
            for slot_id in state:
                state[slot_id] = True

        for slot_id in state:
            me = self.get_matrix_element(slot_id, plot_id)
            me.set_active(state[slot_id])
        self.publish_matrix()

    def update_content(self):
        ncols = self.glo.columnCount()
        nrows = self.glo.rowCount()
        for ii in range(nrows):
            for jj in range(ncols):
                item = self.glo.itemAtPosition(ii, jj)
                if item is not None:
                    item.widget().update_content()
