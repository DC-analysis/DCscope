import copy
import html
import threading

import dclab

from PyQt6 import QtCore, QtGui, QtWidgets

from .. import util
from .widgets import DCscopeColorBarItem
from .pipeline_plot_item import PipelinePlotItem, get_axes_labels
from .pipeline_plot_ui import Ui_Form


class ContourSpacingTooLarge(UserWarning):
    pass


class PipelinePlot(QtWidgets.QWidget):
    """Implements the plotting pipeline using pyqtgraph"""
    # widgets emit these whenever they changed the pipeline
    pp_mod_send = QtCore.pyqtSignal(dict)
    # widgets receive these so they can reflect the pipeline changes
    pp_mod_recv = QtCore.pyqtSignal(dict)

    instances = {}

    def __init__(self, parent, pipeline, plot_id, *args, **kwargs):
        # keeps window from resizing when user updates the plot
        self._resize_lock = threading.Lock()

        super(PipelinePlot, self).__init__(parent=parent, *args, **kwargs)

        self.ui = Ui_Form()
        self.ui.setupUi(self)

        # used to avoid unnecessary plotting
        self._plot_data_hash = "unset"
        self._plot_data_hash_lock = threading.Lock()

        self._window_decoration_size = (None, None)

        #: Contains the PipelinePlotItems
        self.plot_items = []
        self.pipeline = pipeline
        self.identifier = plot_id
        self.update_content()
        PipelinePlot.instances[plot_id] = self

        self.pp_mod_recv.connect(self.on_pp_mod_recv)

    @QtCore.pyqtSlot(dict)
    def on_pp_mod_recv(self, data):
        pip_data = data.get("pipeline", {})
        if pip_data:
            # OK, so we would like to only update the plot when necessary.
            # It is less error prone to exclude known cases than to
            # explicitly state when the plot should update. We definitely
            # want the plots to update when filters are added/removed etc.
            if (
                # Another plot got updated
                pip_data.get(
                    "plot_changed", self.identifier) != self.identifier
                # A plot was created. Ignore that.
                or pip_data.get(
                    "plot_created", self.identifier) != self.identifier
                # A plot was removed.
                or pip_data.get("plot_removed")
            ):
                pass
            else:
                plot = self.pipeline.get_plot(self.identifier)
                plot_state = plot.__getstate__()
                self.update_content()
                if plot.__getstate__() != plot_state:
                    # Updated the range controls
                    self.pp_mod_send.emit({"pipeline-rendering": {
                        "plot_range_corrected": self.identifier,
                    }})

    @QtCore.pyqtSlot(QtGui.QResizeEvent)
    def resizeEvent(self, a0: QtGui.QResizeEvent | None):
        if (a0 is not None
            and self.identifier
                and not self._resize_lock.locked()):
            # Update the plot parameters
            plot_index = self.pipeline.plot_ids.index(self.identifier)
            with self.pipeline.lock:
                state = self.pipeline.plots[plot_index].__getstate__()
                state["layout"]["size x"] = a0.size().width()
                state["layout"]["size y"] = a0.size().height()
                self.pipeline.plots[plot_index].__setstate__(state)
            self.pp_mod_send.emit(
                {"pipeline-rendering": {"plot_size_changed": self.identifier}})

    @QtCore.pyqtSlot()
    def update_content(self):
        """Update the current plot"""
        parent: QtWidgets.QWidget = self.parent()  # type: ignore
        dslist, slot_states = self.pipeline.get_plot_datasets(self.identifier)
        plot = self.pipeline.get_plot(self.identifier)
        plot_state = plot.__getstate__()
        # check whether anything changed
        # 1. plot state and all relevant slot states
        tohash = [slot_states, plot_state]
        # 2. all relevant filter states
        for slot_state in slot_states:
            slot_id = slot_state["identifier"]
            for filt_id in self.pipeline.filter_ids:
                if self.pipeline.is_element_active(slot_id, filt_id):
                    filt = self.pipeline.get_filter(filt_id)
                    filt_state = filt.__getstate__()
                    tohash.append([slot_id, filt_id, filt_state])
                    # also check whether the polygon filters changed (#26)
                    for pid in filt_state["polygon filters"]:
                        pf = dclab.PolygonFilter.get_instance_from_id(pid)
                        tohash.append(pf.__getstate__())
        plot_data_hash = util.hashobj(tohash)
        with self._plot_data_hash_lock:
            if plot_data_hash == self._plot_data_hash:
                # do nothing
                pass
            else:
                self._plot_data_hash = plot_data_hash
                self.update_content_plot(plot_state, slot_states, dslist)

        # Set size in the end (after layout is populated)
        lay = plot_state["layout"]
        wsize_x = lay["size x"] + (self._window_decoration_size[0] or 8)
        wsize_y = lay["size y"] + (self._window_decoration_size[1] or 28)

        with self._resize_lock:
            parent.resize(QtCore.QSize(wsize_x, wsize_y))

        if self._window_decoration_size[0] is None:
            psize = parent.sizeHint()
            csize = self.sizeHint()
            if (psize.width() == wsize_x
                and psize.height() == wsize_y
                and psize.width() > csize.width()
                    and psize.height() > csize.height()):
                # We successfully set the size of the parent window. This
                # means that we can now compute the window decoration size.
                self._window_decoration_size = (
                    psize.width() - csize.width(),
                    psize.height() - csize.height())
        self.ui.plot_layout.updateGeometry()
        self.update()

    def update_content_plot(self, plot_state, slot_states, dslist):
        # abbreviations
        lay = plot_state["layout"]
        sca = plot_state["scatter"]

        # create a hash set for the dcnum hashes
        hash_set = set()
        for ds in dslist:
            pipe_config = ds.config.get("pipeline", {})
            dcnum_hash = pipe_config.get("dcnum hash", None)
            if dcnum_hash is not None:
                hash_set.add(dcnum_hash)
            else:
                hash_set.add(None)

        # title
        self.setWindowTitle(lay["name"])

        # clear widget
        self.ui.plot_layout.clear()

        # set background to white
        self.ui.plot_layout.setBackground("w")

        if not slot_states:
            return

        labelx, labely = get_axes_labels(plot_state, slot_states)

        # font size for plot title (default size + 2)
        size = "{}pt".format(QtGui.QFont().pointSize() + 2)
        self.ui.plot_layout.addLabel(html.escape(lay["name"]),
                                     colspan=3,
                                     size=size)
        self.ui.plot_layout.nextRow()

        self.ui.plot_layout.addLabel(labely, angle=-90)
        linner = self.ui.plot_layout.addLayout()
        linner.setContentsMargins(0, 0, 0, 0)  # reallocate some space

        self.plot_items.clear()

        # limits in case of scatter plot and feature hue
        if lay["division"] == "merge":
            pp = PipelinePlotItem(parent=linner)
            self.plot_items.append(pp)
            linner.addItem(item=pp,
                           row=None,
                           col=None,
                           rowspan=1,
                           colspan=1)
            pp.redraw(dslist, slot_states, plot_state)
        elif lay["division"] == "each":
            colcount = 0
            for ds, sl in zip(dslist, slot_states):
                # get the hash flag
                hash_flag = get_hash_flag(hash_set, ds)

                pp = PipelinePlotItem(parent=linner)
                self.plot_items.append(pp)
                linner.addItem(item=pp,
                               row=None,
                               col=None,
                               rowspan=1,
                               colspan=1)
                pp.redraw([ds], [sl], plot_state, hash_flag)
                colcount += 1
                if colcount % lay["column count"] == 0:
                    linner.nextRow()
        elif lay["division"] == "multiscatter+contour":
            colcount = 0
            # scatter plots
            plot_state_scatter = copy.deepcopy(plot_state)
            plot_state_scatter["contour"]["enabled"] = False
            for ds, sl in zip(dslist, slot_states):
                # get the hash flag
                hash_flag = get_hash_flag(hash_set, ds)

                pp = PipelinePlotItem(parent=linner)
                self.plot_items.append(pp)
                linner.addItem(item=pp,
                               row=None,
                               col=None,
                               rowspan=1,
                               colspan=1)
                pp.redraw([ds], [sl], plot_state_scatter, hash_flag)
                colcount += 1
                if colcount % lay["column count"] == 0:
                    linner.nextRow()
            # contour plot
            plot_state_contour = copy.deepcopy(plot_state)
            plot_state_contour["scatter"]["enabled"] = False
            pp = PipelinePlotItem(parent=linner)
            self.plot_items.append(pp)
            linner.addItem(item=pp,
                           row=None,
                           col=None,
                           rowspan=1,
                           colspan=1)
            pp.redraw(dslist, slot_states, plot_state_contour)

        elif lay["division"] == "onlycontours":
            # contour plots
            plot_state_contour = copy.deepcopy(plot_state)
            plot_state_contour["scatter"]["enabled"] = False
            pp = PipelinePlotItem(parent=linner)
            self.plot_items.append(pp)
            linner.addItem(item=pp,
                           row=None,
                           col=None,
                           rowspan=1,
                           colspan=1)
            pp.redraw(dslist, slot_states, plot_state_contour)

        # colorbar
        colorbar_kwds = {}

        if sca["marker hue"] == "kde":
            colorbar_kwds["values"] = (0, 1)
            colorbar_kwds["label"] = "density [a.u.]"
        elif sca["marker hue"] == "feature":
            feat = sca["hue feature"]
            label = dclab.dfn.get_feature_label(feat)
            fl_names = slot_states[0]["fl names"]
            if label.count("FL"):
                for key in fl_names:
                    if key in label:
                        label = label.replace(key, fl_names[key])
                        break
            colorbar_kwds["label"] = label
            if label.endswith("[a.u.]"):
                colorbar_kwds["values"] = (0, 1)
            else:
                colorbar_kwds["values"] = (sca["hue min"], sca["hue max"])

        if colorbar_kwds:
            # add colorbar
            colorbar = DCscopeColorBarItem(
                yoffset=31,  # this is heuristic
                height=min(300, lay["size y"] // 2),
                color_map_name=sca["colormap"],
                interactive=False,
                width=15,
                **colorbar_kwds
            )
            self.ui.plot_layout.addItem(colorbar)

        # x-axis label
        self.ui.plot_layout.nextRow()
        self.ui.plot_layout.addLabel(labelx, col=1)


def get_hash_flag(hash_set, rtdc_ds):
    """Helper function to determine the hash flag based on the dataset and
    hash set."""
    if len(hash_set) == 1:
        # only one hash, no need to show it
        return None

    req_hash_len = 4
    # get the longest hash from the hash set
    longest_hash = max((h for h in hash_set if h), key=len, default="temphash")

    # find the minimum and unique hash length dynamically
    for char_len in range(req_hash_len, len(longest_hash)):
        temp_short_hash_set = set(
            h[:char_len] if h is not None else None for h in hash_set
        )
        if len(temp_short_hash_set) != len(hash_set):
            req_hash_len += 1
        else:
            break

    # get the pipeline hash
    pipe_config = rtdc_ds.config.get("pipeline", {})
    dcnum_hash = pipe_config.get("dcnum hash", None)
    # use the first `req_hash_len` characters of the hash
    short_hash = dcnum_hash[:req_hash_len] if dcnum_hash else None
    return f"Pipeline {short_hash}" if short_hash else None
