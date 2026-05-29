import html
import threading

import dclab
import numpy as np
import pyqtgraph as pg
from dclab.kde import KernelDensityEstimator

from PyQt6 import QtCore, QtGui, QtTest, QtWidgets
from pyqtgraph import exporters

from .tasks import TaskManager
from .widgets import SimplePlotItem
from .pipeline_plot_compute import (
    compute_contours_from_state,
    compute_contour_reliable,
    compute_scatter_data_from_state,
)


linestyles = {
    "solid": QtCore.Qt.PenStyle.SolidLine,
    "dashed": QtCore.Qt.PenStyle.DashLine,
    "dotted": QtCore.Qt.PenStyle.DotLine,
}


class PipelinePlotItem(SimplePlotItem):
    def __init__(self, task_manager: TaskManager, *args, **kwargs):
        """A pipeline plot item is one subplot"""
        super(PipelinePlotItem, self).__init__(*args, **kwargs)
        self.tm = task_manager
        self.tm.task_done.connect(self.request_scatter_handler)

        self._task_data = []
        # circumvent problems with removed plots
        self.setAcceptHoverEvents(False)
        # Disable user interaction
        self.setMouseEnabled(x=False, y=False)
        # bring axes to front
        self.axes_to_front()
        # Keep track of all elements (for redraw)
        self._plot_elements = []
        # Set background to white (for plot export)
        self.vb.setBackgroundColor("w")

        self._update_lock = threading.Lock()

        self.state_data: dict = None  # type: ignore

    def perform_export(self, file):
        """Performs export of this subplot in new layout with axes labels set

        Overrides the basic functionality of SimplePlotItem.
        See https://github.com/DC-analysis/DCscope/issues/7
        """
        # Create a plot window
        win = pg.GraphicsLayoutWidget(
            size=(int(self.width() + 100), int(self.height() + 100)),
            show=True)
        # fill layout
        labelx, labely = get_axes_labels(self.state_data["plot_state"],
                                         self.state_data["slot_states"])
        win.addLabel(labely, angle=-90)

        tm = TaskManager(None)
        explot = PipelinePlotItem(task_manager=tm)
        explot.request_draw(**self.state_data)
        while tm.num_tasks:
            QtTest.QTest.qWait(100)
        tm.close()

        win.addItem(explot)
        win.addLabel("")  # spacer to avoid cut tick labels on the right(#7)
        win.nextRow()
        win.addLabel(labelx, col=1)
        # Update the UI (do it twice, otherwise the tick labels overlap)
        QtWidgets.QApplication.processEvents(
            QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
        win.hide()
        # perform actual export
        suffix = file[-3:]
        if suffix == "png":
            exp = exporters.ImageExporter(win.scene())
            # translate from screen resolution (80dpi) to 300dpi
            exp.params["width"] = int(exp.params["width"] / 72 * 300)
        elif suffix == "svg":
            exp = exporters.SVGExporter(win.scene())
        else:
            raise ValueError(f"Invalid suffix '{suffix}'")
        exp.export(file)
        win.deleteLater()

    def request_draw(self, dslist, slot_states, plot_state, hash_flag=None):
        # Remove everything
        for el in self._plot_elements:
            self.removeItem(el)
        self._plot_elements.clear()

        if not dslist:
            return

        self.state_data = {
            "dslist": dslist,
            "slot_states": slot_states,
            "plot_state": plot_state,
            "hash_flag": hash_flag,
        }

        # General
        gen = plot_state["general"]
        # Isoelastics
        if gen["isoelastics"]:
            cfg = dslist[0].config
            els = add_isoelastics(plot_item=self,
                                  axis_x=gen["axis x"],
                                  axis_y=gen["axis y"],
                                  channel_width=cfg["setup"]["channel width"],
                                  pixel_size=cfg["imaging"]["pixel size"],
                                  lut_identifier=gen.get("lut", None))
            self._plot_elements += els
        # Modifications in log mode
        set_viewbox(self,
                    range_x=gen["range x"],
                    range_y=gen["range y"],
                    scale_x=gen["scale x"],
                    scale_y=gen["scale y"])
        # Scatter data
        sca = plot_state["scatter"]
        if sca["enabled"]:
            for rtdc_ds, ss in zip(dslist, slot_states):
                self.request_scatter(
                    rtdc_ds=rtdc_ds,
                    plot_state=plot_state,
                    slot_state=ss,
                    )
        # Contour data
        if plot_state["contour"]["enabled"]:
            # show legend
            if plot_state["contour"]["legend"]:
                legend = self.addLegend(offset=(-.01, +.01))
            else:
                legend = None
            for rtdc_ds, ss in zip(dslist, slot_states):
                if plot_state["contour"].get("zoomin", False):
                    zoomin_contours(dslist=dslist,
                                    plot_item=self,
                                    plot_state=plot_state
                                    )
                con = add_contour(plot_item=self,
                                  rtdc_ds=rtdc_ds,
                                  plot_state=plot_state,
                                  slot_state=ss,
                                  legend=legend,
                                  )
                self._plot_elements += con

        # Set subplot title and number of events
        if plot_state["layout"]["label plots"]:
            if len(dslist) == 1 and plot_state["scatter"]["enabled"]:
                # only one scatter plot
                ss = slot_states[0]
                self.setTitle("")  # fake title
                add_label(text=html.escape(ss["name"]),
                          anchor_parent=self.titleLabel.item,
                          color=ss["color"],
                          text_halign="center",
                          text_valign="top",
                          dx=4
                          )

            elif (plot_state["contour"]["enabled"]
                    and not plot_state["scatter"]["enabled"]):
                # only a contour plot
                self.setTitle("")  # fake title
                add_label(text="Contours",
                          color="black",
                          anchor_parent=self.titleLabel.item,
                          text_halign="center",
                          text_valign="top",
                          dx=4,
                          )

    def request_scatter(self, plot_state, rtdc_ds, slot_state):
        task = {
            "func": compute_scatter_data_from_state,
            "kwargs": {"plot_state": plot_state,
                       "rtdc_ds": rtdc_ds,
                       "slot_state": slot_state,
                       }
            }

        with self._update_lock:
            self._task_data.append(task)

        self.tm.add_task(
            task=task,
            topic="pipeline-plot",
            )

    @QtCore.pyqtSlot(dict, object)
    def request_scatter_handler(self, task: dict, result: tuple):
        if task not in self._task_data:
            # ignore events from different plot items
            return

        plot_state = self.state_data["plot_state"]
        hash_flag = self.state_data["hash_flag"]
        x, y, _, _, brush = result

        gen = plot_state["general"]
        sca = plot_state["scatter"]
        scatter = pg.ScatterPlotItem(size=sca["marker size"],
                                     pen=pg.mkPen(color=(0, 0, 0, 0)),
                                     brush=pg.mkBrush("k"),
                                     symbol="s")
        scatter.setAcceptHoverEvents(False)

        with self._update_lock:
            self.addItem(scatter)

        # convert to log-scale if applicable
        if gen["scale x"] == "log":
            x = np.log10(x)
        if gen["scale y"] == "log":
            y = np.log10(y)

        # add dcnum hash label
        if hash_flag:
            add_label(
                hash_flag,
                anchor_parent=self.axes["top"]["item"],
                font_size_diff=-1,
                color="red",
                text_halign="left",
                text_valign="top",
            )

        if (plot_state["scatter"]["show event count"]
                and len(self.state_data["dslist"]) == 1):
            add_label(
                text=f"{len(x)} events",
                anchor_parent=self.axes["right"]["item"],
                font_size_diff=-1,
                color="black",
                text_halign="right",
                text_valign="top",
                dx=2,
                dy=-5,
            )

        scatter.setData(x=x, y=y, brush=brush)
        scatter.setZValue(-50)
        with self._update_lock:
            self._task_data.remove(task)
            self._plot_elements.append(scatter)


def add_contour(plot_item, plot_state, rtdc_ds, slot_state, legend=None):
    contours = compute_contours_from_state(plot_state=plot_state,
                                           rtdc_ds=rtdc_ds)
    con = plot_state["contour"]
    elements = []
    num_unreliable_contours = 0
    for ii in range(len(contours)):
        style = linestyles[con["line styles"][ii]]
        width = con["line widths"][ii]
        for cci in contours[ii]:
            if not compute_contour_reliable(plot_state=plot_state,
                                            contour=cci):
                num_unreliable_contours += 1
            cline = pg.PlotDataItem(x=cci[:, 0],
                                    y=cci[:, 1],
                                    pen=pg.mkPen(color=slot_state["color"],
                                                 width=width,
                                                 style=style,
                                                 ),
                                    )
            elements.append(cline)
            plot_item.addItem(cline)
            if ii == 0 and legend is not None:
                legend.addItem(cline, slot_state["name"])
            # Always plot higher percentiles above lower percentiles
            # (useful if there are multiple contour plots overlapping)
            cline.setZValue(con["percentiles"][ii])

    label = ""
    if not KernelDensityEstimator.check_feat_kde_applicability(
        xax=plot_state["general"]["axis x"],
            yax=plot_state["general"]["axis y"]):
        label = "Contour data unavailable"
    elif num_unreliable_contours or not elements:
        # Tell the user to refine KDE spacing.
        label = "Please reduce KDE spacing"
    if label:
        add_label(label,
                  anchor_parent=plot_item.axes["bottom"]["item"],
                  font_size_diff=-1,
                  color="red",
                  text_halign="left",
                  text_valign="bottom",
                  dy=-12,
                  )

    return elements


def add_isoelastics(plot_item, axis_x, axis_y, channel_width, pixel_size,
                    lut_identifier=None):
    elements = []
    isodef = dclab.isoelastics.get_default()
    # We do not use isodef.get_with_rtdcbase, because then the
    # isoelastics would be shifted according to flow rate and.
    # viscosity. We could do it, but for visualization there is
    # really no need and also, the plots then look the same as
    # in DCscope 1.
    try:
        iso = isodef.get(
            lut_identifier=lut_identifier if lut_identifier
            else "LE-2D-FEM-19",
            channel_width=channel_width,
            flow_rate=None,
            viscosity=None,
            col1=axis_x,
            col2=axis_y,
            add_px_err=True,
            px_um=pixel_size)
    except KeyError:
        pass
    else:
        for ss in iso:
            iline = pg.PlotDataItem(x=ss[:, 0], y=ss[:, 1])
            plot_item.addItem(iline)
            elements.append(iline)
            # send them to the back
            iline.setZValue(-100)
    return elements


def add_label(text, anchor_parent, text_halign="center", text_valign="center",
              font_size_diff=0, color=None, dx=0, dy=0):
    """Add a graphics label anchored to another item

    This is a hackish workaround that was made more elaborate
    due to https://github.com/DC-analysis/DCscope/issues/33.

    Parameters
    ----------
    text: str
        Label text (no HTML!)
    anchor_parent: QGraphicsItem
        Anything in the plot (e.g. axis items or other labels) that can
        be anchored to. This object will be the parent of the label.
    text_halign: str
        Horizontal text alignment relative to anchor point
        ("left", "center", "right")
    text_valign: str
        Vertical text alignment relative to anchor point
        ("left", "center", "right")
    font_size_diff: int
        Change font size of text relative to `QtGui.QFont().pointSize()`
        (is added via css)
    color: str
        Color of the text (is added via css)
    dx: float
        Manual horizontal positioning
    dy: float
        Manual vertical positioning
    """
    assert text_halign in ["left", "center", "right"]
    assert text_valign in ["top", "center", "bottom"]
    font_size = QtGui.QFont().pointSize() + font_size_diff
    css = "font-size:{}pt;".format(font_size)
    if color is not None:
        css += "color:{};".format(color)
    html = "<span style='{}'>{}</span>".format(css, text)
    label = QtWidgets.QGraphicsTextItem(
        "",
        # This is kind of hackish: set the parent to the right
        # axis so that it is always drawn there.
        parent=anchor_parent)
    label.setHtml(html)

    # move label
    width = label.boundingRect().width()
    height = label.boundingRect().height()
    if text_halign == "center":
        x = -width / 2
    elif text_halign == "left":
        x = 0
    else:  # "right"
        x = -width

    if text_valign == "center":
        y = -height / 2
    elif text_valign == "top":
        y = 0
    else:  # "bottom"
        y = -height/2
    label.setPos(x + dx, y + dy)


def get_axes_labels(plot_state, slot_states):
    gen = plot_state["general"]
    # Use slot_states[0] because we only have one x-axis label
    labelx = get_axis_label_from_feature(gen["axis x"], slot_states[0])
    labely = get_axis_label_from_feature(gen["axis y"], slot_states[0])
    return labelx, labely


def get_axis_label_from_feature(feat, slot_state=None):
    """Return the axis label for plotting given a feature name

    - replace the fluorescence names with user-defined strings
      from `slot_state["fl names"]` if `slot_state` is given
    - html-escape all characters
    """
    label = dclab.dfn.get_feature_label(feat)
    # replace FL-? with user-defined names
    if slot_state is not None and "fl names" in slot_state:
        fl_names = slot_state["fl names"]
        if label.count("FL") and feat.startswith("fl"):
            for key in fl_names:
                if key in label:
                    label = label.replace(key, fl_names[key])
                    break
    return html.escape(label)


def set_viewbox(plot, range_x, range_y, scale_x="linear", scale_y="linear",
                padding=0.):
    # Set Log scale
    plot.setLogMode(x=scale_x == "log",
                    y=scale_y == "log")
    range_x = np.array(range_x)
    range_y = np.array(range_y)
    if scale_x == "log":
        if range_x[0] <= 0:
            if range_x[1] > 10:
                range_x[0] = 1e-1
            else:
                range_x[0] = 1e-3
        range_x = np.log10(range_x)
    if scale_y == "log":
        if range_y[0] <= 0:
            if range_y[1] > 10:
                range_y[0] = 1e-1
            else:
                range_y[0] = 1e-3
        range_y = np.log10(range_y)
    # Set Range
    plot.setRange(xRange=range_x,
                  yRange=range_y,
                  padding=padding,
                  )


def zoomin_contours(dslist, plot_item, plot_state, margin_per=5):
    """Zoom-in contour data if enabled"""
    x_min, x_max, y_min, y_max = 0, 0, 0, 0
    # compute all contours
    contours_list = [compute_contours_from_state(plot_state, ds)
                     for ds in dslist]
    # flatten list of contours
    all_points = np.vstack([np.vstack(c) for conts in contours_list
                            for c in conts])

    if all_points.size > 0:
        x_min = np.min(all_points[:, 0])
        x_max = np.max(all_points[:, 0])
        y_min = np.min(all_points[:, 1])
        y_max = np.max(all_points[:, 1])

    # Add margin
    x_margin = (x_max - x_min) * margin_per*0.01
    y_margin = (y_max - y_min) * margin_per*0.01

    # Set view range with margins
    plot_item.setRange(
        xRange=(x_min - x_margin, x_max + x_margin),
        yRange=(y_min - y_margin, y_max + y_margin),
        padding=0
    )
