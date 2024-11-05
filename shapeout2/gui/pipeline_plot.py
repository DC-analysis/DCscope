import copy
import html
import importlib.resources
import warnings

import dclab
from dclab import kde_contours
import numpy as np
from PyQt6 import uic, QtCore, QtGui, QtWidgets
import pyqtgraph as pg
from pyqtgraph import exporters
from pyqtgraph.graphicsItems.GradientEditorItem import Gradients


from .. import plot_cache
from .. import util
from .widgets import ShapeOutColorBarItem

from .widgets import SimplePlotItem


# Register custom colormaps
Gradients["grayblue"] = {'ticks': [(0.0, (100, 100, 100, 255)),
                                   (1.0, (0, 0, 255, 255))],
                         'mode': 'rgb'}

Gradients["graygreen"] = {'ticks': [(0.0, (100, 100, 100, 255)),
                                    (1.0, (0, 180, 0, 255))],
                          'mode': 'rgb'}

Gradients["grayorange"] = {'ticks': [(0.0, (100, 100, 100, 255)),
                                     (1.0, (210, 110, 0, 255))],
                           'mode': 'rgb'}

Gradients["grayred"] = {'ticks': [(0.0, (100, 100, 100, 255)),
                                  (1.0, (200, 0, 0, 255))],
                        'mode': 'rgb'}


class ContourSpacingTooLarge(UserWarning):
    pass


class PipelinePlot(QtWidgets.QWidget):
    """Implements the plotting pipeline using pyqtgraph"""
    instances = {}

    def __init__(self, parent, pipeline, plot_id, *args, **kwargs):
        super(PipelinePlot, self).__init__(parent=parent, *args, **kwargs)
        ref = importlib.resources.files("shapeout2.gui") / "pipeline_plot.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        # used to avoid unnecessary plotting
        self._plot_data_hash = "unset"

        #: Contains the PipelinePlotItems
        self.plot_items = []
        self.pipeline = pipeline
        self.identifier = plot_id
        self.update_content()
        PipelinePlot.instances[plot_id] = self

    def update_content(self):
        """Update the current plot"""
        parent = self.parent()
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
        if plot_data_hash == self._plot_data_hash:
            # do nothing
            return
        else:
            self._plot_data_hash = plot_data_hash

        # abbreviations
        gen = plot_state["general"]
        lay = plot_state["layout"]
        sca = plot_state["scatter"]

        # auto range (overrides stored ranges)
        if gen["auto range"]:
            # default range is limits + 5% margin
            gen["range x"] = self.pipeline.get_min_max(feat=gen["axis x"],
                                                       plot_id=self.identifier,
                                                       margin=.05)
            gen["range y"] = self.pipeline.get_min_max(feat=gen["axis y"],
                                                       plot_id=self.identifier,
                                                       margin=0.05)

        # title
        self.setWindowTitle(lay["name"])

        # clear widget
        self.plot_layout.clear()

        # set background to white
        self.plot_layout.setBackground("w")

        if not slot_states:
            return

        labelx, labely = get_axes_labels(plot_state, slot_states)

        # font size for plot title (default size + 2)
        size = "{}pt".format(QtGui.QFont().pointSize() + 2)
        self.plot_layout.addLabel(html.escape(lay["name"]),
                                  colspan=3,
                                  size=size)
        self.plot_layout.nextRow()

        self.plot_layout.addLabel(labely, angle=-90)
        linner = self.plot_layout.addLayout()
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
                pp = PipelinePlotItem(parent=linner)
                self.plot_items.append(pp)
                linner.addItem(item=pp,
                               row=None,
                               col=None,
                               rowspan=1,
                               colspan=1)
                pp.redraw([ds], [sl], plot_state)
                colcount += 1
                if colcount % lay["column count"] == 0:
                    linner.nextRow()
        elif lay["division"] == "multiscatter+contour":
            colcount = 0
            # scatter plots
            plot_state_scatter = copy.deepcopy(plot_state)
            plot_state_scatter["contour"]["enabled"] = False
            for ds, sl in zip(dslist, slot_states):
                pp = PipelinePlotItem(parent=linner)
                self.plot_items.append(pp)
                linner.addItem(item=pp,
                               row=None,
                               col=None,
                               rowspan=1,
                               colspan=1)
                pp.redraw([ds], [sl], plot_state_scatter)
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
            cmap = pg.ColorMap(*zip(*Gradients[sca["colormap"]]["ticks"]))
            colorbar = ShapeOutColorBarItem(
                yoffset=31,  # this is heuristic
                height=min(300, lay["size y"] // 2),
                colorMap=cmap,
                interactive=False,
                width=15,
                **colorbar_kwds
            )
            self.plot_layout.addItem(colorbar)

        # x-axis label
        self.plot_layout.nextRow()
        self.plot_layout.addLabel(labelx, col=1)

        # Set size in the end (after layout is populated)
        self.setMinimumSize(lay["size x"], lay["size y"])
        self.setMaximumSize(lay["size x"], lay["size y"])
        size_hint = self.parent().sizeHint()
        parent.setMinimumSize(size_hint)
        parent.setMaximumSize(size_hint)
        self.plot_layout.updateGeometry()


class PipelinePlotItem(SimplePlotItem):
    def __init__(self, *args, **kwargs):
        super(PipelinePlotItem, self).__init__(*args, **kwargs)
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

    def perform_export(self, file):
        """Performs export in new layout with axes labels set

        Overrides the basic functionality of SimplePlotItem.
        See https://github.com/ZELLMECHANIK-DRESDEN/ShapeOut2/issues/7
        """
        # Create a plot window
        win = pg.GraphicsLayoutWidget(
            size=(int(self.width() + 100), int(self.height() + 100)),
            show=True)
        # fill layout
        labelx, labely = get_axes_labels(self.plot_state, self.slot_states)
        win.addLabel(labely, angle=-90)
        explot = PipelinePlotItem()
        explot.redraw(self.dslist, self.slot_states, self.plot_state)
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
        exp.export(file)

    def redraw(self, dslist, slot_states, plot_state):
        # Remove everything
        for el in self._plot_elements:
            self.removeItem(el)

        if not dslist:
            return

        self.dslist = dslist
        self.slot_states = slot_states
        self.plot_state = plot_state

        # General
        gen = plot_state["general"]
        # TODO:
        # - test whether all datasets have same channel width / pixel size
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
                sct = add_scatter(plot_item=self,
                                  rtdc_ds=rtdc_ds,
                                  plot_state=plot_state,
                                  slot_state=ss
                                  )
                self._plot_elements += sct
        # Contour data
        if plot_state["contour"]["enabled"]:
            # show legend
            if plot_state["contour"]["legend"]:
                legend = self.addLegend(offset=(-.01, +.01))
            else:
                legend = None
            for rtdc_ds, ss in zip(dslist, slot_states):
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

                if plot_state["scatter"]["show event count"]:
                    if True:
                        add_label(text=f"{len(sct[0].data)} events",
                                  anchor_parent=self.axes["right"]["item"],
                                  font_size_diff=-1,
                                  color="black",
                                  text_halign="right",
                                  text_valign="top",
                                  dx=2,
                                  dy=-5,
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


def add_label(text, anchor_parent, text_halign="center", text_valign="center",
              font_size_diff=0, color=None, dx=0, dy=0):
    """Add a graphics label anchored to another item

    This is a hackish workaround that was made more elaborate
    due to https://github.com/ZELLMECHANIK-DRESDEN/ShapeOut2/issues/33.

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


def add_contour(plot_item, plot_state, rtdc_ds, slot_state, legend=None):
    contours = compute_contours(plot_state=plot_state, rtdc_ds=rtdc_ds)
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
    if num_unreliable_contours or not elements:
        # Tell the user to refine contour spacing.
        add_label("Please reduce contour spacing.",
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
    # in Shape-Out 1.
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


def add_scatter(plot_item, plot_state, rtdc_ds, slot_state):
    gen = plot_state["general"]
    sca = plot_state["scatter"]
    scatter = pg.ScatterPlotItem(size=sca["marker size"],
                                 pen=pg.mkPen(color=(0, 0, 0, 0)),
                                 brush=pg.mkBrush("k"),
                                 symbol="s")
    scatter.setAcceptHoverEvents(False)
    plot_item.addItem(scatter)

    if sca["marker hue"] == "kde":
        kde_type = gen["kde"]
    else:
        kde_type = "none"

    x, y, kde, idx = plot_cache.get_scatter_data(
        rtdc_ds=rtdc_ds,
        downsample=sca["downsample"] * sca["downsampling value"],
        xax=gen["axis x"],
        yax=gen["axis y"],
        xscale=gen["scale x"],
        yscale=gen["scale y"],
        kde_type=kde_type,
    )
    # define colormap
    # TODO:
    # - common code base with QuickView
    cmap = pg.ColorMap(*zip(*Gradients[sca["colormap"]]["ticks"]))
    if sca["marker hue"] == "kde":
        brush = []
        # Note: we don't expand the density to [0, 1], because the
        # colorbar will show "density" and because we don want to
        # compute the density in this function and not someplace else.
        for k in kde:
            brush.append(cmap.mapToQColor(k))
        # Note, colors could also be digitized (does not seem to be faster):
        # cbin = np.linspace(0, 1, 1000)
        # dig = np.digitize(kde, cbin)
        # for idx in dig:
        #     brush.append(cmap.mapToQColor(cbin[idx]))
    elif sca["marker hue"] == "feature":
        brush = []
        feat = np.asarray(rtdc_ds[sca["hue feature"]][idx], dtype=float)
        feat -= sca["hue min"]
        feat /= sca["hue max"] - sca["hue min"]
        for f in feat:
            if np.isnan(f):
                brush.append(pg.mkColor("#FF0000"))
            else:
                brush.append(cmap.mapToQColor(f))
    elif sca["marker hue"] == "dataset":
        alpha = int(sca["marker alpha"] * 255)
        colord = pg.mkColor(slot_state["color"])
        colord.setAlpha(alpha)
        brush = pg.mkBrush(colord)
    else:
        alpha = int(sca["marker alpha"] * 255)
        colork = pg.mkColor("#000000")
        colork.setAlpha(alpha)
        brush = pg.mkBrush(colork)

    # convert to log-scale if applicable
    if gen["scale x"] == "log":
        x = np.log10(x)
    if gen["scale y"] == "log":
        y = np.log10(y)

    scatter.setData(x=x, y=y, brush=brush)
    scatter.setZValue(-50)
    return [scatter]


def compute_contours(plot_state, rtdc_ds):
    gen = plot_state["general"]
    con = plot_state["contour"]
    try:
        x, y, density = plot_cache.get_contour_data(
            rtdc_ds=rtdc_ds,
            xax=gen["axis x"],
            yax=gen["axis y"],
            xacc=con["spacing x"],
            yacc=con["spacing y"],
            xscale=gen["scale x"],
            yscale=gen["scale y"],
            kde_type=gen["kde"],
        )
    except ValueError:
        # most-likely there is nothing to compute a contour for
        return []
    if density.shape[0] < 3 or density.shape[1] < 3:
        warnings.warn("Contour not possible; spacing may be too large!",
                      ContourSpacingTooLarge)
        return []
    plev = kde_contours.get_quantile_levels(
        density=density,
        x=x,
        y=y,
        xp=rtdc_ds[gen["axis x"]][rtdc_ds.filter.all],
        yp=rtdc_ds[gen["axis y"]][rtdc_ds.filter.all],
        q=np.array(con["percentiles"]) / 100,
        normalize=True)
    contours = []
    for level in plev:
        # make sure that the contour levels are not at the boundaries
        if not (np.allclose(level, 0, atol=1e-12, rtol=0)
                or np.allclose(level, 1, atol=1e-12, rtol=0)):
            cc = kde_contours.find_contours_level(
                density, x=x, y=y, level=level)
            contours.append(cc)
    return contours


def compute_contour_opening_angles(plot_state, contour):
    """For each point of the contour, compute the opening angle

    This takes the visible plot area into account.
    """
    cc = np.array(contour, copy=True)
    if not np.all(cc[0] == cc[-1]):
        cc = np.resize(cc, (len(contour)+1, 2))
    # Normalize contour
    rx = plot_state["general"]["range x"]
    ry = plot_state["general"]["range y"]
    cc[:, 0] = (cc[:, 0] - rx[0]) / (rx[1] - rx[0])
    cc[:, 1] = (cc[:, 1] - ry[0]) / (ry[1] - ry[0])
    # apply scale
    sx = plot_state["general"]["scale x"]
    assert sx in ["log", "linear"]
    if sx == "log":
        cc[:, 0] = np.log10(cc[:, 0])
    sy = plot_state["general"]["scale y"]
    assert sy in ["log", "linear"]
    if sy == "log":
        cc[:, 1] = np.log10(cc[:, 1])
    opang = np.zeros(len(cc)-1, dtype=float)
    for jj, c0 in enumerate(cc[:-1]):  # we have a closed contour
        cl = cc[:-1][jj - 1]
        cr = cc[jj + 1]
        # vector a
        a = np.array(cl) - np.array(c0)
        # vector b
        b = np.array(cr) - np.array(c0)
        absa = np.sqrt(np.sum(a ** 2))
        absb = np.sqrt(np.sum(b ** 2))
        denom = absa * absb
        # avoid division by zero warnings
        if isinstance(denom, np.ndarray):
            denom[denom == 0] = np.nan
        elif denom == 0:
            denom = np.nan
        phi = np.arccos(np.sum(a * b) / denom)
        if np.abs(phi) > np.pi/2:
            phi -= np.sign(phi) * np.pi
        opang[jj] = phi
    return opang


def compute_contour_reliable(plot_state, contour, thresh_ang=np.deg2rad(23)):
    """Determine whether contour is reliable or not"""
    # Compute the opening angle for each point of the
    # contour and take the point with the largest opening angle.
    angles = compute_contour_opening_angles(
        plot_state=plot_state, contour=contour)
    if (np.allclose(np.abs(angles[0]), np.pi / 2)
            and np.all(angles[1:6] == 0)):
        # We have probably encountered a contour at the boundary
        # of the image. It looks like this is ok.
        reliable = True
    elif len(angles) > 50:
        # The contour is long enough to be trusted.
        reliable = True
    else:
        reliable = np.max(np.abs(angles)) <= thresh_ang
    return reliable


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
                padding=0):
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


linestyles = {
    "solid": QtCore.Qt.PenStyle.SolidLine,
    "dashed": QtCore.Qt.PenStyle.DashLine,
    "dotted": QtCore.Qt.PenStyle.DotLine,
}
