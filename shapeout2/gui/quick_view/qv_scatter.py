import numpy as np
from PyQt6 import QtCore
import pyqtgraph as pg
from pyqtgraph.graphicsItems.GradientEditorItem import Gradients

from ... import plot_cache

from .. import pipeline_plot
from ..widgets import SimplePlotWidget, SimpleViewBox


class QuickViewScatterWidget(SimplePlotWidget):
    update_hover_pos = QtCore.pyqtSignal(QtCore.QPointF)

    def __init__(self, *args, **kwargs):
        self._view_box = QuickViewViewBox()
        super(QuickViewScatterWidget, self).__init__(viewBox=self._view_box,
                                                     *args, **kwargs)
        self._view_box.update_hover_pos.connect(self.update_hover_pos)
        self.scatter = RTDCScatterPlot()
        self.select = pg.PlotDataItem(x=[1], y=[2], symbol="o")
        #: List of isoelasticity line plots
        self.isoelastics = []
        self.addItem(self.scatter)
        self.addItem(self.select)
        self.select.hide()
        self.xscale = "linear"
        self.yscale = "linear"
        self.kde_type = "none",
        self.kde_kwargs = {}
        self.hue_type = "none"
        self.hue_kwargs = {}
        #: Boolean array identifying the plotted events w.r.t. the full
        #: dataset
        self.events_plotted = None
        #: Unfiltered and not-downsampled x component of current scatter plot
        self.data_x = None
        #: Unfiltered and not-downsampled y component of current scatter plot
        self.data_y = None

        # polygon editing ROI
        self.poly_line_roi = None

        # Signals for mouse click
        # let view box update the selected event in the scatter plot
        self._view_box.set_scatter_point.connect(self.scatter.set_point)
        # let view box update self.poly_line_roi
        self._view_box.add_poly_vertex.connect(self.add_poly_vertex)

    def activate_poly_mode(self, points=None):
        if points is None:
            points = []
        if self.poly_line_roi is None:
            self.poly_line_roi = pg.PolyLineROI([], closed=True)
            self.poly_line_roi.setPen("k")
        self.addItem(self.poly_line_roi)
        if len(points):
            mode = "poly-modify"
            self.set_poly_points(points)
        else:
            mode = "poly-create"
        self.set_mouse_click_mode(mode)
        return self.poly_line_roi

    def activate_scatter_mode(self):
        if self.poly_line_roi is not None:
            self.removeItem(self.poly_line_roi)
            self.poly_line_roi = None
        self.set_mouse_click_mode("scatter")

    def add_poly_vertex(self, pos):
        state = self.poly_line_roi.getState()
        state["points"].append([pos.x(), pos.y()])
        self.poly_line_roi.setState(state)

    def get_poly_points(self):
        if self.poly_line_roi is None:
            raise ValueError("No polygon selection active!")
        state = self.poly_line_roi.getState()
        points = np.array([[p.x(), p.y()] for p in state["points"]])
        # Take into account manual movements of the entire ROI (issue #115)
        points[:, 0] += state["pos"][0]
        points[:, 1] += state["pos"][1]
        if self.xscale == "log":
            points[:, 0] = 10**points[:, 0]
        if self.yscale == "log":
            points[:, 1] = 10**points[:, 1]
        return points

    def plot_data(self, rtdc_ds, slot, xax="area_um", yax="deform",
                  xscale="linear", yscale="linear",  downsample=False,
                  hue_type="none", hue_kwargs=None, isoelastics=False,
                  lut_identifier=None):
        self.rtdc_ds = rtdc_ds
        self.slot = slot
        self.xax = xax
        self.yax = yax
        self.xscale = xscale
        self.yscale = yscale
        self.hue_type = hue_type
        self.hue_kwargs = hue_kwargs if hue_kwargs else {}
        if hue_type != "kde":
            self.kde_type = "none"
            self.kde_kwargs = {}
        else:
            self.kde_type = hue_kwargs["kde_type"]
            self.kde_kwargs = hue_kwargs.get("kde_kwargs")
        x, y, kde, idx = plot_cache.get_scatter_data(
            rtdc_ds=self.rtdc_ds,
            downsample=downsample,
            xax=self.xax,
            yax=self.yax,
            xscale=self.xscale,
            yscale=self.yscale,
            kde_type=self.kde_type,
            kde_kwargs=self.kde_kwargs)
        self.events_plotted = idx
        #: unfiltered x data
        self.data_x = self.rtdc_ds[self.xax]
        #: unfiltered y data
        self.data_y = self.rtdc_ds[self.yax]
        if self.hue_type == "none":
            brush = "k"
        else:
            # define colormap
            brush = []
            cmap = pg.ColorMap(*zip(*Gradients["viridis"]["ticks"]))
            if self.hue_type == "kde":
                for k in kde:
                    brush.append(cmap.mapToQColor(k))
            elif self.hue_type == "feature":
                fdata = self.rtdc_ds[self.hue_kwargs["feat"]][idx]
                fdata -= fdata.min()
                fdata = np.array(fdata, dtype=float)  # cast int to float
                fdata /= fdata.max()
                for f in fdata:
                    brush.append(cmap.mapToQColor(f))

        if x.size:  # test for empty x/y (#37)
            # set viewbox
            pipeline_plot.set_viewbox(plot=self,
                                      range_x=(x.min(), x.max()),
                                      range_y=(y.min(), y.max()),
                                      scale_x=self.xscale,
                                      scale_y=self.yscale,
                                      padding=0.05)
        # set data
        self.setData(x, y, brush=brush)
        # set axes labels (replace with user-defined flourescence names)
        left = pipeline_plot.get_axis_label_from_feature(
            self.yax, slot_state=self.slot.__getstate__())
        bottom = pipeline_plot.get_axis_label_from_feature(
            self.xax, slot_state=self.slot.__getstate__())
        self.plotItem.setLabels(left=left, bottom=bottom)

        # Force updating the plot item size, otherwise axes labels
        # may have an offset.
        s = self.plotItem.size()
        self.plotItem.resize(s.width()+1, s.height())
        self.plotItem.resize(s)

        # Isoelastics
        # remove old isoelastics
        for lp in self.isoelastics:
            self.removeItem(lp)
        if isoelastics:
            cfg = self.rtdc_ds.config
            self.isoelastics = pipeline_plot.add_isoelastics(
                plot_item=self.plotItem,
                axis_x=self.xax,
                axis_y=self.yax,
                channel_width=cfg["setup"]["channel width"],
                pixel_size=cfg["imaging"]["pixel size"],
                lut_identifier=lut_identifier)

    def set_mouse_click_mode(self, mode):
        allowed = ["scatter", "poly-create", "poly-modify"]
        if mode not in allowed:
            raise ValueError("Invalid mouse mode: {}, ".format(mode)
                             + "expected one of {}".format(allowed))
        if mode in ["poly-create", "poly-modify"]:
            if self.poly_line_roi is None:
                raise ValueError("Please set self.poly_line_roi before "
                                 + "setting the click mode!")
        self._view_box.mode = mode

    def set_poly_points(self, points):
        if self.poly_line_roi is None:
            raise ValueError("No polygon selection active!")
        points = np.array(points, copy=True)
        if points.size:
            if self.xscale == "log":
                points[:, 0] = np.log10(points[:, 0])
            if self.yscale == "log":
                points[:, 1] = np.log10(points[:, 1])
            state = self.poly_line_roi.getState()
            state["points"] = points.tolist()
            self.poly_line_roi.setState(state)

    def setData(self, x, y, **kwargs):
        # convert to log-scale if applicable
        if self.xscale == "log":
            x = np.log10(x)
        if self.yscale == "log":
            y = np.log10(y)
        # set data
        self.scatter.setData(x=x, y=y, **kwargs)

    def setSelection(self, event_index):
        x = self.data_x[event_index]
        y = self.data_y[event_index]
        self.select.setData([x], [y])


class QuickViewViewBox(SimpleViewBox):
    set_scatter_point = QtCore.pyqtSignal(QtCore.QPointF)
    add_poly_vertex = QtCore.pyqtSignal(QtCore.QPointF)
    update_hover_pos = QtCore.pyqtSignal(QtCore.QPointF)

    def __init__(self, *args, **kwargs):
        super(QuickViewViewBox, self).__init__(*args, **kwargs)
        self.mode = "scatter"

        #: allowed right-click menu options with new name
        self.right_click_actions["View All"] = "View All Content"
        self.right_click_actions["Mouse Mode"] = "Change Mouse mode"

    def mouseClickEvent(self, ev):
        if ev.button() == QtCore.Qt.MouseButton.LeftButton:
            pos = self.mapToView(ev.pos())
            if self.mode == "scatter":
                self.set_scatter_point.emit(pos)
            elif self.mode == "poly-create":
                self.add_poly_vertex.emit(pos)
            ev.accept()
        else:
            # right mouse button shows menu
            super(QuickViewViewBox, self).mouseClickEvent(ev)

    def hoverEvent(self, ev):
        if hasattr(ev, "_scenePos"):
            pos = self.mapToView(ev.pos())
            self.update_hover_pos.emit(pos)


class RTDCScatterPlot(pg.ScatterPlotItem):
    def __init__(self, size=3, pen=None, brush=None, *args, **kwargs):
        if pen is None:
            pen = pg.mkPen(color=(0, 0, 0, 0))
        if brush is None:
            brush = pg.mkBrush("k")
        super(RTDCScatterPlot, self).__init__(size=size,
                                              pen=pen,
                                              brush=brush,
                                              symbol="s",
                                              *args,
                                              **kwargs)
        self.setData(x=range(10), y=range(10), brush=brush)

    def pointAt(self, pos):
        """Unlike `ScatterPlotItem.pointsAt`, return the closest point"""
        x = pos.x()
        y = pos.y()

        pw = self.pixelWidth()
        ph = self.pixelHeight()

        # compute the distances of all points to x and y
        dists = np.abs((self.data["x"] - x)/pw) \
            + np.abs((self.data["y"] - y)/ph)
        ide = np.argmin(dists)

        # calling `self.points` populates the data["item"] column.
        return self.points()[ide]

    def set_point(self, view_pos):
        pos = self.mapFromView(view_pos)
        pt = self.pointAt(pos)
        self.ptClicked = pt
        self.sigClicked.emit(self, self.ptClicked, None)

    def mouseClickEvent(self, ev):
        """Override that does not handle events"""
        ev.ignore()  # clicks are handles by CustomViewBox
