import collections
import importlib.resources
import logging
import pathlib

import dclab
import numpy as np
from PyQt6 import QtCore, QtWidgets
import pyqtgraph as pg

from ... import idiom, util

from ..compute.comp_stats import STAT_METHODS
from ..widgets import show_wait_cursor

from .qv_event_getter import EventGetterThread
from .import qv_image_vis as qvvis
from .qv_main_ui import Ui_Form


#: default choices for x-axis in plots in descending order
AXES_DEFAULT_CHOICES_X = [
    "area_um", "index", "frame", "index_online", "time",
]
#: default choices for y-axis in plots in descending order
AXES_DEFAULT_CHOICES_Y = [
    "deform", "bright_avg", "bright_bc_avg", "bg_med", "index",
]


logger = logging.getLogger(__name__)


class QuickView(QtWidgets.QWidget):
    polygon_filter_about_to_be_deleted = QtCore.pyqtSignal(int)

    # widgets emit these whenever they changed the pipeline
    pp_mod_send = QtCore.pyqtSignal(dict)
    # widgets receive these so they can reflect the pipeline changes
    pp_mod_recv = QtCore.pyqtSignal(dict)

    def __init__(self, *args, **kwargs):
        self._hover_ds_id = None
        self._hover_event_idx = None
        super(QuickView, self).__init__(*args, **kwargs)

        self.ui = Ui_Form()
        self.ui.setupUi(self)

        self.pipeline = None
        self.current_pipeline_element = None
        self._last_event_data = None
        self._last_cmap_pha = {}

        # set event view as default page
        self.ui.stackedWidget.setCurrentIndex(1)
        self.ui.groupBox_image.setVisible(False)
        self.ui.groupBox_trace.setVisible(False)
        self.ui.imageView_image.setVisible(False)
        self.ui.imageView_image_amp.setVisible(False)
        self.ui.imageView_image_pha.setVisible(False)

        ref = importlib.resources.files(
            "dcscope.gui.quick_view") / "qv_style.css"
        with importlib.resources.as_file(ref) as path_css:
            stylesheet = pathlib.Path(path_css).read_text()
        self.ui.groupBox_image.setStyleSheet(stylesheet)
        self.ui.groupBox_trace.setStyleSheet(stylesheet)
        self.ui.comboBox_x.default_choices = AXES_DEFAULT_CHOICES_X
        self.ui.comboBox_y.default_choices = AXES_DEFAULT_CHOICES_Y

        self.setWindowTitle("Quick View")

        self._set_initial_ui()

        # Set scale options (with data)
        for cb in [self.ui.comboBox_xscale, self.ui.comboBox_yscale]:
            cb.clear()
            cb.addItem("linear", "linear")
            cb.addItem("logarithmic", "log")

        # Set marker hue options (with data)
        self.ui.comboBox_hue.clear()
        self.ui.comboBox_hue.addItem("KDE", "kde")
        self.ui.comboBox_hue.addItem("feature", "feature")

        # Set look-up table options for isoelasticity lines
        self.ui.comboBox_lut.clear()
        lut_dict = dclab.features.emodulus.load.get_internal_lut_names_dict()
        for lut_id in lut_dict.keys():
            self.ui.comboBox_lut.addItem(lut_id, lut_id)
        # Set LE-2D-FEM-19 as a default
        idx = self.ui.comboBox_lut.findData("LE-2D-FEM-19")
        self.ui.comboBox_lut.setCurrentIndex(idx)

        # settings button
        self.ui.toolButton_event.toggled.connect(self.on_tool)
        self.ui.toolButton_poly.toggled.connect(self.on_tool)
        self.ui.toolButton_settings.toggled.connect(self.on_tool)

        # polygon filter signals
        self.ui.label_poly_create.setVisible(False)
        self.ui.label_poly_modify.setVisible(False)
        self.ui.pushButton_poly_save.setVisible(False)
        self.ui.pushButton_poly_cancel.setVisible(False)
        self.ui.pushButton_poly_delete.setVisible(False)
        self.ui.pushButton_poly_create.clicked.connect(self.on_poly_create)
        self.ui.pushButton_poly_save.clicked.connect(self.on_poly_done_save)
        self.ui.pushButton_poly_cancel.clicked.connect(
            self.on_poly_done_cancel)
        self.ui.pushButton_poly_delete.clicked.connect(
            self.on_poly_done_delete)
        self.ui.comboBox_poly.currentIndexChanged.connect(self.on_poly_modify)
        self.update_polygon_panel()

        # event changed signal
        self.ui.widget_scatter.scatter.sigClicked.connect(
            self.on_event_scatter_clicked)
        self.ui.widget_scatter.update_hover_pos.connect(
            self.on_event_scatter_hover)
        self.ui.spinBox_event.valueChanged.connect(self.on_event_scatter_spin)
        self.ui.checkBox_image_contour.stateChanged.connect(
            self.on_event_scatter_update)
        self.ui.checkBox_image_contrast.stateChanged.connect(
            self.on_event_scatter_update)
        self.ui.checkBox_image_zoom.stateChanged.connect(
            self.on_event_scatter_update)
        self.ui.checkBox_image_background.stateChanged.connect(
            self.on_event_scatter_update)
        self.ui.checkBox_trace_raw.stateChanged.connect(
            self.on_event_scatter_update)
        self.ui.checkBox_trace_legend.stateChanged.connect(
            self.on_event_scatter_update)
        self.ui.checkBox_trace_zoom.stateChanged.connect(
            self.on_event_scatter_update)
        self.ui.tabWidget_event.currentChanged.connect(
            self.on_event_scatter_update)

        # apply button
        self.ui.toolButton_apply.clicked.connect(self.plot)
        # value changed signals for plot
        self.signal_widgets = [self.ui.checkBox_downsample,
                               self.ui.spinBox_downsample,
                               self.ui.comboBox_x,
                               self.ui.comboBox_y,
                               self.ui.comboBox_xscale,
                               self.ui.comboBox_yscale,
                               self.ui.checkBox_isoelastics,
                               self.ui.comboBox_z_hue,
                               self.ui.comboBox_hue,
                               self.ui.checkBox_hue,
                               self.ui.comboBox_lut
                               ]
        for w in self.signal_widgets:
            if hasattr(w, "currentIndexChanged"):
                w.currentIndexChanged.connect(self.plot_auto)
            elif hasattr(w, "stateChanged"):
                w.stateChanged.connect(self.plot_auto)
            elif hasattr(w, "valueChanged"):
                w.valueChanged.connect(self.plot_auto)
        # copy statistics to clipboard
        self.ui.toolButton_stats2clipboard.clicked.connect(
            self.on_stats2clipboard)

        # Set individual plots
        kw0 = dict(x=np.arange(10), y=np.arange(10))
        self.trace_plots = {
            "fl1_raw": pg.PlotDataItem(pen="#6EA068", **kw0),  # green
            "fl2_raw": pg.PlotDataItem(pen="#8E7A45", **kw0),  # orange
            "fl3_raw": pg.PlotDataItem(pen="#8F4D48", **kw0),  # red
            "fl1_median": pg.PlotDataItem(pen="#15BF00", **kw0),  # green
            "fl2_median": pg.PlotDataItem(pen="#BF8A00", **kw0),  # orange
            "fl3_median": pg.PlotDataItem(pen="#BF0C00", **kw0),  # red
        }
        for key in self.trace_plots:
            self.ui.graphicsView_trace.addItem(self.trace_plots[key])
            self.trace_plots[key].setVisible(False)

        self.ui.graphicsView_trace.plotItem.setLabels(
            left="Fluorescence [a.u.]", bottom="Event time [µs]")
        self.legend_trace = self.ui.graphicsView_trace.addLegend(
            offset=(-.01, +.01))

        #: dictionary access to image views
        self.img_views = {
            "image": {
                "view_event": self.ui.imageView_image,
                "view_poly": self.ui.imageView_image_poly,
            },
            "qpi_pha": {
                "view_event": self.ui.imageView_image_pha,
                "view_poly": self.ui.imageView_image_poly_pha,
            },
            "qpi_amp": {
                "view_event": self.ui.imageView_image_amp,
                "view_poly": self.ui.imageView_image_poly_amp,
            },
        }

        # The event getter runs in the background
        self.event_getter = EventGetterThread(self)
        self.event_getter.new_event_data.connect(self.on_getter_new_event)
        self.event_getter.busy_fetching_data.connect(self.on_getter_busy)

        self.event_getter.start()

        # set initial empty dataset
        self._rtdc_ds = None
        self.slot = None
        #: A cache for the event index plotted for a dataset
        self._dataset_event_plot_indices_cache = {}

        self._statistics_cache = collections.OrderedDict()

        self.pp_mod_recv.connect(self.on_pp_mod_recv)

    def _set_initial_ui(self):
        self._hover_ds_id = None
        self._hover_event_idx = None
        # events label
        self.ui.label_noevents.setVisible(False)
        self.enable_interface(False)

    @property
    def rtdc_ds(self):
        """Dataset to plot; set to None initially and if the file is closed"""
        if self._rtdc_ds is not None:
            if not util.check_file_open(self._rtdc_ds):
                self._rtdc_ds = None
        # now check again
        if self._rtdc_ds is None:
            self._set_initial_ui()
        return self._rtdc_ds

    @rtdc_ds.setter
    def rtdc_ds(self, rtdc_ds):
        if self._rtdc_ds is not rtdc_ds:
            self._hover_ds_id = None
            self._hover_event_idx = None

        self._rtdc_ds = rtdc_ds

        # Hide "Subtract Background"-Checkbox if feature
        # "image_bg" not in dataset
        contains_bg_feat = "image_bg" in rtdc_ds
        self.ui.checkBox_image_background.setVisible(contains_bg_feat)

        # set the dataset for the FeatureComboBoxes
        self.ui.comboBox_x.set_dataset(rtdc_ds)
        self.ui.comboBox_y.set_dataset(rtdc_ds)
        self.ui.comboBox_z_hue.set_dataset(rtdc_ds)

    def close(self):
        self.event_getter.close()
        super(QuickView, self).close()

    @QtCore.pyqtSlot(dict)
    def on_pp_mod_recv(self, data):
        qv_dict = data.get("quickview")
        if qv_dict and qv_dict.get("enabled"):
            ds = self.pipeline.get_dataset(slot_index=qv_dict["slot_index"],
                                           filt_index=qv_dict["filt_index"])
            self.show_rtdc(rtdc_ds=ds,
                           slot=self.pipeline.slots[qv_dict["slot_index"]])
            self.current_pipeline_element = qv_dict

        if data.get("pipeline") and self.isVisible():
            # fetch the slot from the pipeline
            if self.current_pipeline_element is not None:
                slot_id = self.current_pipeline_element["slot_id"]
                filt_id = self.current_pipeline_element["filt_id"]
                try:
                    slot_index = self.pipeline.slot_ids.index(slot_id)
                    filt_index = self.pipeline.filter_ids.index(filt_id)
                    ds = self.pipeline.get_dataset(slot_index=slot_index,
                                                   filt_index=filt_index)
                    self.show_rtdc(rtdc_ds=ds,
                                   slot=self.pipeline.slots[slot_index])
                except BaseException:
                    logger.debug(f"Could not find element for QuickView: "
                                 f"{self.current_pipeline_element}")
                    self.current_pipeline_element = None
                    self.enable_interface(False)

            self.update_polygon_panel()

    def read_pipeline_state(self):
        plot = {
            "downsampling": self.ui.checkBox_downsample.isChecked(),
            "downsampling value": self.ui.spinBox_downsample.value(),
            "axis x": self.ui.comboBox_x.currentData(),
            "axis y": self.ui.comboBox_y.currentData(),
            "scale x": self.ui.comboBox_xscale.currentData(),
            "scale y": self.ui.comboBox_yscale.currentData(),
            "isoelastics": self.ui.checkBox_isoelastics.isChecked(),
            "lut": self.ui.comboBox_lut.currentData(),
            "marker hue": self.ui.checkBox_hue.isChecked(),
            "marker hue value": self.ui.comboBox_hue.currentData(),
            "marker hue feature": self.ui.comboBox_z_hue.currentData(),
        }
        event = {
            "index": self.ui.spinBox_event.value(),
            "image auto contrast": self.ui.checkBox_image_contrast.isChecked(),
            "image contour": self.ui.checkBox_image_contour.isChecked(),
            "image zoom": self.ui.checkBox_image_zoom.isChecked(),
            "image background": self.ui.checkBox_image_background.isChecked(),
            "trace legend": self.ui.checkBox_trace_legend.isChecked(),
            "trace raw": self.ui.checkBox_trace_raw.isChecked(),
            "trace zoom": self.ui.checkBox_trace_zoom.isChecked(),
        }
        state = {
            "plot": plot,
            "event": event,
        }
        return state

    def write_pipeline_state(self, state):
        plot = state["plot"]
        for tb in self.signal_widgets:
            tb.blockSignals(True)
        # downsampling
        self.ui.checkBox_downsample.setChecked(plot["downsampling"])
        self.ui.spinBox_downsample.setValue(plot["downsampling value"])
        self.ui.checkBox_hue.setChecked(plot["marker hue"])
        # combo box key selection
        self.update_feature_choices()
        for key, cb in [
            # axes labels
            ("axis x", self.ui.comboBox_x),
            ("axis y", self.ui.comboBox_y),
            # scaling
            ("scale x", self.ui.comboBox_xscale),
            ("scale y", self.ui.comboBox_yscale),
            # look up table
            ("lut", self.ui.comboBox_lut),
            # marker hue
            ("marker hue value", self.ui.comboBox_hue),
            ("marker hue feature", self.ui.comboBox_z_hue),
        ]:
            idx = cb.findData(plot[key])
            idx = idx if idx > 0 else 0
            cb.setCurrentIndex(idx)

        # isoelastics
        self.ui.checkBox_isoelastics.setChecked(plot["isoelastics"])
        for tb in self.signal_widgets:
            tb.blockSignals(False)
        if "event" in state:
            event = state["event"]
            self.ui.checkBox_image_contrast.setChecked(
                event["image auto contrast"])
            self.ui.checkBox_image_contour.setChecked(event["image contour"])
            self.ui.checkBox_image_zoom.setChecked(event["image zoom"])
            self.ui.checkBox_image_background.setChecked(
                event["image background"])
            self.ui.spinBox_event.setValue(event["index"])
            self.ui.checkBox_trace_raw.setChecked(event["trace raw"])
            self.ui.checkBox_trace_legend.setChecked(event["trace legend"])

    def enable_interface(self, value):
        # Initially, only show the info about how QuickView works
        self.ui.widget_tool.setEnabled(value)
        self.ui.widget_scatter.setVisible(value)
        # stacked widget
        self.ui.stackedWidget.setEnabled(value)
        # how-to label
        self.ui.label_howto.setVisible(not value)

        if not value:
            self.ui.imageView_image.setImage(np.full((10, 10), 200))
            self.ui.imageView_image_amp.setImage(np.full((10, 10), 200))
            self.ui.imageView_image_pha.setImage(np.full((10, 10), 200))

    @QtCore.pyqtSlot(bool)
    def on_getter_busy(self, busy):
        if busy:
            color = "orange"
            tooltip = "fetching event data"
        else:
            color = "black"
            tooltip = "event data updated"
        self.ui.widget_waiter.setStyleSheet(
            f"background-color:{color};border-radius:7px")
        self.ui.widget_waiter.setToolTip(tooltip)

    @QtCore.pyqtSlot(dict)
    def on_getter_new_event(self, data):
        self._last_event_data = data

        if self.ui.page_poly.isVisible():
            view_key = "view_poly"
        else:
            view_key = "view_event"

        # Image data
        if "image" in data or "qpi_pha" in data or "qpi_amp" in data:
            self.ui.groupBox_image.setVisible(True)
        else:
            self.ui.groupBox_image.setVisible(False)

        for feat in ["image", "qpi_pha", "qpi_amp"]:
            view = self.img_views[feat][view_key]
            if feat in data:
                self.show_image(feat, view, data)
                view.setVisible(True)
            else:
                view.setVisible(False)

        # Trace data
        if "traces" in data:
            self.ui.groupBox_trace.setVisible(True)
            self.show_traces(data["traces"])
        else:
            self.ui.groupBox_trace.setVisible(False)

    def show_image(self, feat, view, data):
        cell_img, vmin, vmax, cmap = qvvis.get_rgb_image(
            data=data,
            feat=feat,
            zoom=self.ui.checkBox_image_zoom.isChecked(),
            draw_contour=self.ui.checkBox_image_contour.isChecked(),
            auto_contrast=self.ui.checkBox_image_contrast.isChecked(),
            subtract_background=self.ui.checkBox_image_background.isChecked(),
        )

        view.setImage(cell_img,
                      autoLevels=False,
                      levels=(vmin, vmax)
                      )

        if feat == "qpi_pha" and cmap != self._last_cmap_pha.get(view):
            view.setColorMap(cmap)
            self._last_cmap_pha[view] = cmap

    def show_traces(self, tdata):
        state = self.read_pipeline_state()
        # remove legend items
        for item in reversed(self.legend_trace.items):
            self.legend_trace.removeItem(item[1].text)
        self.legend_trace.setVisible(state["event"]["trace legend"])

        # temporal range (min, max)
        if state["event"]["trace zoom"]:
            range_t = [np.inf, -np.inf]
        else:
            range_t = [tdata["time"][0], tdata["time"][-1]]
        # fluorescence intensity
        range_fl = [0, 0]

        for name in dclab.dfn.FLUOR_TRACES:
            if name.count("raw") and not state["event"]["trace raw"]:
                # hide raw trace data if user decided so
                show = False
            else:
                show = True
            flid = name.split("_")[0]
            if name in tdata and show:
                range_fl[0] = min(range_fl[0], tdata[name].min())
                range_fl[1] = max(range_fl[1], tdata[name].max())
                self.trace_plots[name].setData(tdata["time"], tdata[name])
                self.trace_plots[name].setVisible(True)
                if state["event"]["trace zoom"]:
                    range_t[0] = min(
                        range_t[0],
                        tdata[f"{flid}_pos"] - 1.5 * tdata[f"{flid}_width"]
                    )
                    range_t[1] = max(
                        range_t[1],
                        tdata[f"{flid}_pos"] + 1.5 * tdata[f"{flid}_width"]
                    )
                # set legend name
                ln = self.slot.fl_name_dict[f"FL-{name[2]}"] + f" {name[4:]}"
                self.legend_trace.addItem(self.trace_plots[name], ln)
                self.legend_trace.update()
            else:
                self.trace_plots[name].setVisible(False)
        self.ui.graphicsView_trace.setXRange(*range_t, padding=0)
        if range_fl[0] != range_fl[1]:
            self.ui.graphicsView_trace.setYRange(*range_fl, padding=.01)
        self.ui.graphicsView_trace.setLimits(xMin=0, xMax=tdata["time"][-1])

    # Statistics
    ############
    def get_statistics(self):
        if self.rtdc_ds is not None:
            features = [self.ui.comboBox_x.currentData(),
                        self.ui.comboBox_y.currentData()]
            # cache statistics from
            dsid = "-".join(features
                            + [self.rtdc_ds.identifier,
                               self.rtdc_ds.filter._parent_hash]
                            )
            if dsid not in self._statistics_cache:
                stats = dclab.statistics.get_statistics(ds=self.rtdc_ds,
                                                        features=features,
                                                        methods=STAT_METHODS)
                self._statistics_cache[dsid] = stats
            if len(self._statistics_cache) > 1000:
                # avoid a memory leak
                self._statistics_cache.popitem(last=False)
            return self._statistics_cache[dsid]
        else:
            return None, None

    # Scatter Plot
    ##############
    @QtCore.pyqtSlot(object, object)
    def on_event_scatter_clicked(self, plot, point):
        """User clicked on scatter plot

        Parameters
        ----------
        plot: pg.PlotItem
            Active plot
        point: QPoint
            Selected point (determined by scatter plot widget)
        """
        if self.ui.widget_scatter.events_plotted is not None:
            # plotted events
            plotted = self.ui.widget_scatter.events_plotted
            # get corrected index
            ds_idx = np.where(plotted)[0][point.index()]
            self.show_event(ds_idx)
        # Note that triggering the toolButton_event must be done after
        # calling show_event, otherwise the first event is shown and
        # only after that the desired one. This would be a drawback when
        # events come from remote locations.
        #
        # `self.on_tool` (`self.ui.toolButton_event`) takes care of this:
        # self.ui.widget_scatter.select.setVisible(True)
        if not self.ui.toolButton_event.isChecked():
            # emulate mouse toggle
            self.ui.toolButton_event.setChecked(True)
            self.ui.toolButton_event.toggled.emit(True)

    @QtCore.pyqtSlot(QtCore.QPointF)
    def on_event_scatter_hover(self, pos):
        """Update the image view in the polygon widget """
        if self.rtdc_ds is not None and self.ui.toolButton_poly.isChecked():
            ds = self.rtdc_ds
            # plotted events
            plotted = self.ui.widget_scatter.events_plotted
            spos = self.ui.widget_scatter.scatter.mapFromView(pos)
            point = self.ui.widget_scatter.scatter.pointAt(spos)
            # get corrected index
            event = np.where(plotted)[0][point.index()]

            # Only plot if we have not plotted this event before
            if (self._hover_ds_id != id(ds)
                    or self._hover_event_idx != event):
                # remember where we were
                self._hover_ds_id = id(ds)
                self._hover_event_idx = event

                self.event_getter.request_event_data(ds, event)

    @QtCore.pyqtSlot(int)
    def on_event_scatter_spin(self, event):
        """Sping control for event selection changed"""
        self.show_event(event - 1)

    @QtCore.pyqtSlot()
    def on_event_scatter_update(self):
        """Just update the event shown"""
        if self._last_event_data:
            self.on_getter_new_event(self._last_event_data)

    # Polygon Selection
    ###################
    @QtCore.pyqtSlot()
    def on_poly_create(self):
        """User wants to create a polygon filter"""
        self.ui.toolButton_poly.setChecked(True)
        self.ui.pushButton_poly_create.setEnabled(False)
        self.ui.comboBox_poly.setEnabled(False)
        self.ui.groupBox_poly.setEnabled(True)
        self.ui.label_poly_create.setVisible(True)
        self.ui.label_poly_modify.setVisible(False)
        self.ui.pushButton_poly_save.setVisible(True)
        self.ui.pushButton_poly_cancel.setVisible(True)
        # defaults
        self.ui.lineEdit_poly.setText("Polygon Filter {}".format(
            dclab.PolygonFilter._instance_counter + 1))
        self.ui.checkBox_poly.setChecked(False)
        self.ui.widget_scatter.activate_poly_mode()
        # trigger resize and redraw
        mdiwin = self.parent()
        mdiwin.adjustSize()
        mdiwin.update()
        self.update()

    @QtCore.pyqtSlot()
    def on_poly_done(self, mode="none"):
        """User is done creating or modifying a polygon filter"""
        self.ui.pushButton_poly_create.setEnabled(True)
        self.ui.label_poly_create.setVisible(False)
        self.ui.label_poly_modify.setVisible(False)
        self.ui.pushButton_poly_save.setVisible(False)
        self.ui.pushButton_poly_cancel.setVisible(False)
        self.ui.pushButton_poly_delete.setVisible(False)
        # remove the PolyLineRoi
        self.ui.widget_scatter.activate_scatter_mode()
        self.update_polygon_panel()
        idp = self.ui.comboBox_poly.currentData()
        if mode == "create":
            self.pp_mod_send.emit({"filter": {"polygon_filter_added": idp}})
        elif mode == "modify":
            self.pp_mod_send.emit(
                {"pipeline": {"polygon_filter_modified": idp}})

    @QtCore.pyqtSlot()
    def on_poly_done_delete(self):
        # delete the polygon filter
        idp = self.ui.comboBox_poly.currentData()
        if idp is not None:
            # There is a polygon filter that we want to delete
            self.polygon_filter_about_to_be_deleted.emit(idp)
            dclab.PolygonFilter.remove(idp)
            mode = "modify"
        else:
            mode = "none"
        self.on_poly_done(mode)

    @QtCore.pyqtSlot()
    def on_poly_done_cancel(self):
        self.on_poly_done()

    @QtCore.pyqtSlot()
    def on_poly_done_save(self):
        # save the polygon filter
        points = self.ui.widget_scatter.get_poly_points()
        name = self.ui.lineEdit_poly.text()
        inverted = self.ui.checkBox_poly.isChecked()
        axes = self.ui.widget_scatter.xax, self.ui.widget_scatter.yax
        # determine whether to create a new polygon filter or whether
        # to update an existing one.
        idp = self.ui.comboBox_poly.currentData()
        if idp is None:
            dclab.PolygonFilter(axes=axes, points=points, name=name,
                                inverted=inverted)
            mode = "create"
        else:
            pf = dclab.PolygonFilter.get_instance_from_id(idp)
            pf.name = name
            pf.inverted = inverted
            pf.points = points
            mode = "modify"
        self.on_poly_done(mode)

    @QtCore.pyqtSlot()
    def on_poly_modify(self, polygon_filter_id=None):
        """User wants to modify a polygon filter"""
        self.ui.toolButton_poly.setChecked(True)
        self.ui.pushButton_poly_create.setEnabled(False)
        self.ui.comboBox_poly.setEnabled(False)
        self.ui.groupBox_poly.setEnabled(True)
        self.ui.label_poly_modify.setVisible(True)
        self.ui.pushButton_poly_save.setVisible(True)
        self.ui.pushButton_poly_cancel.setVisible(True)
        self.ui.pushButton_poly_delete.setVisible(True)
        if polygon_filter_id is None:
            # get the polygon filter id
            polygon_filter_id = self.ui.comboBox_poly.currentData()
        pf = dclab.PolygonFilter.get_instance_from_id(polygon_filter_id)
        # set UI information
        self.ui.lineEdit_poly.setText(pf.name)
        self.ui.checkBox_poly.setChecked(pf.inverted)
        # set axes
        state = self.read_pipeline_state()
        state["plot"]["axis x"] = pf.axes[0]
        state["plot"]["axis y"] = pf.axes[1]
        self.write_pipeline_state(state)
        self.plot()
        # add ROI
        self.ui.widget_scatter.activate_poly_mode(pf.points)

    # Buttons
    #########
    @QtCore.pyqtSlot()
    def on_stats2clipboard(self):
        """Copy the statistics as tsv data to the clipboard"""
        h, v = self.get_statistics()
        if h is not None:
            # assemble tsv data
            tsv = ""
            for hi, vi in zip(h, v):
                tsv += "{}\t{:.7g}\n".format(hi, vi)
            QtWidgets.qApp.clipboard().setText(tsv)

    @show_wait_cursor
    @QtCore.pyqtSlot()
    def on_tool(self, collapse=False):
        """Show and hide tools when the user selected a tool button"""
        toblock = [self.ui.toolButton_event,
                   self.ui.toolButton_poly,
                   self.ui.toolButton_settings,
                   ]
        for b in toblock:
            b.blockSignals(True)

        # show extra data
        show_event = False
        show_poly = False
        show_settings = False
        sender = self.sender()

        if sender in toblock:
            # prevent a tool buttons from unchecking itself
            sender.setChecked(True)

        if sender == self.ui.toolButton_event:
            show_event = self.ui.toolButton_event.isChecked()
        elif sender == self.ui.toolButton_poly:
            show_poly = self.ui.toolButton_poly.isChecked()
        elif sender == self.ui.toolButton_settings:
            show_settings = self.ui.toolButton_settings.isChecked()
        elif collapse:
            # show nothing
            pass
        else:
            # keep everything as-is but update the sizes
            cur_widget = self.ui.stackedWidget.currentWidget()
            show_event = cur_widget is self.ui.page_event
            show_settings = cur_widget is self.ui.page_settings
            show_poly = cur_widget is self.ui.page_poly

        # toolbutton checked
        self.ui.toolButton_event.setChecked(show_event)
        self.ui.toolButton_poly.setChecked(show_poly)
        self.ui.toolButton_settings.setChecked(show_settings)

        # stack widget visibility
        if show_event:
            self.ui.stackedWidget.setCurrentWidget(self.ui.page_event)
        elif show_settings:
            self.ui.stackedWidget.setCurrentWidget(self.ui.page_settings)
        elif show_poly:
            self.ui.stackedWidget.setCurrentWidget(self.ui.page_poly)

        self.ui.widget_scatter.select.setVisible(
            show_event)  # point in scatter

        if show_event:
            # update event plot (maybe axes changed)
            self.on_event_scatter_update()

        for b in toblock:
            b.blockSignals(False)

        if not show_poly:
            self.on_poly_done()

        self.update()

    @show_wait_cursor
    @QtCore.pyqtSlot()
    def plot(self):
        """Update the plot using the current state of the UI"""
        if self.rtdc_ds is not None:
            plot = self.read_pipeline_state()["plot"]
            downsample = plot["downsampling"] * plot["downsampling value"]
            hue_kwargs = {}
            if self.ui.checkBox_hue.isChecked():
                hue_type = self.ui.comboBox_hue.currentData()
                if hue_type == "kde":
                    hue_kwargs = {"kde_type": "histogram"}
                if hue_type == "feature":
                    hue_kwargs = {"feat": self.ui.comboBox_z_hue.currentData()}
            else:
                hue_type = "none"

            self.ui.widget_scatter.plot_data(rtdc_ds=self.rtdc_ds,
                                             slot=self.slot,
                                             downsample=downsample,
                                             xax=plot["axis x"],
                                             yax=plot["axis y"],
                                             xscale=plot["scale x"],
                                             yscale=plot["scale y"],
                                             hue_type=hue_type,
                                             hue_kwargs=hue_kwargs,
                                             isoelastics=plot["isoelastics"],
                                             lut_identifier=plot["lut"])
            # make sure the correct plot items are visible
            # (e.g. scatter select)
            self.on_tool()
            # update polygon filter axis names
            self.ui.label_poly_x.setText(
                dclab.dfn.get_feature_label(plot["axis x"]))
            self.ui.label_poly_y.setText(
                dclab.dfn.get_feature_label(plot["axis y"]))
            self.show_statistics()
            # Make sure features are properly colored in the comboboxes
            self.update_feature_choices()

    @QtCore.pyqtSlot()
    def plot_auto(self):
        """Update the plot only if the "Auto-apply" checkbox is checked"""
        if self.ui.checkBox_auto_apply.isChecked():
            sender = self.sender()
            for cb, sen in [
                (self.ui.checkBox_downsample, [self.ui.spinBox_downsample]),
                (self.ui.checkBox_hue, [self.ui.comboBox_hue,
                                        self.ui.comboBox_z_hue])]:
                # Do not replot if the user changes the options for a
                # disabled settings (e.g. downsampling, hue)
                if sender in sen:
                    if not cb.isChecked():
                        break
            else:
                self.plot()

    def set_pipeline(self, pipeline):
        if self.pipeline is not None:
            raise ValueError("Pipeline can only be set once")
        self.pipeline = pipeline

    @show_wait_cursor
    @QtCore.pyqtSlot(int)
    def show_event(self, event_index):
        """Display the event data (image, contour, trace)

        Parameters
        ----------
        event: int
            Event index of the dataset; indices start at 0
            If set to None, the index from `self.ui.spinBox_event`
            will be used.
        """
        if self.rtdc_ds is None:
            return

        # dataset
        ds = self.rtdc_ds
        self._dataset_event_plot_indices_cache[
            id(self.rtdc_ds.hparent)] = int(event_index)
        event_count = ds.config["experiment"]["event count"]
        if event_count == 0:
            # nothing to do
            return

        # Update spin box data
        self.ui.spinBox_event.blockSignals(True)
        self.ui.spinBox_event.setValue(event_index + 1)
        self.ui.spinBox_event.blockSignals(False)

        # Update selection point in scatter plot
        self.ui.widget_scatter.setSelection(event_index)
        if self.ui.tabWidget_event.currentIndex() == 0:
            # request the data from the event getter
            self.event_getter.request_event_data(ds, event_index)
        else:
            # only use computed features (speed)
            fcands = ds.features_local
            feats = [f for f in fcands if f in ds.features_scalar]
            lf = sorted([(dclab.dfn.get_feature_label(f), f) for f in feats])
            keys = []
            vals = []
            for lii, fii in lf:
                keys.append(lii)
                val = ds[fii][event_index]
                if fii in idiom.INTEGER_FEATURES:
                    val = int(np.round(val))
                vals.append(val)
            self.ui.tableWidget_feats.set_key_vals(keys, vals)

    @show_wait_cursor
    @QtCore.pyqtSlot(object, object)
    def show_rtdc(self, rtdc_ds, slot):
        """Display an RT-DC measurement given by `path` and `filters`"""
        if np.all(rtdc_ds.filter.all) and rtdc_ds.format == "hierarchy":
            # No filers applied, no additional hierarchy child required.
            self.rtdc_ds = rtdc_ds
        else:
            # Create a hierarchy child so that the user can browse
            # comfortably through the data without seeing hidden events.
            self.rtdc_ds = dclab.new_dataset(
                rtdc_ds,
                identifier=f"child-of-{rtdc_ds.identifier}")

        event_count = self.rtdc_ds.config["experiment"]["event count"]
        if event_count == 0:
            self.enable_interface(False)
            self.ui.label_noevents.setVisible(True)
            self.on_tool(collapse=True)
            # reset image view
            self.ui.groupBox_image.setVisible(False)
            self.ui.groupBox_trace.setVisible(False)
            return
        else:
            # make things visible
            self.enable_interface(True)
            self.ui.label_noevents.setVisible(False)

        # get the state
        state = self.read_pipeline_state()
        plot = state["plot"]
        # remove event state (ill-defined for different datasets)
        state.pop("event")

        self.slot = slot

        # check whether axes exist in ds and change them to defaults
        # if necessary
        ds_features = sorted(self.rtdc_ds.features_scalar)
        if plot["axis x"] not in ds_features and ds_features:
            plot["axis x"] = ds_features[0]
        if plot["axis y"] not in ds_features and ds_features:
            if len(ds_features) > 1:
                plot["axis y"] = ds_features[1]
            else:
                # If there is only one feature, at least we
                # have set the state to a reasonable value.
                plot["axis y"] = ds_features[0]

        # set control ranges
        self.ui.spinBox_event.blockSignals(True)
        self.ui.spinBox_event.setMaximum(event_count)
        self.ui.spinBox_event.setToolTip(f"total: {event_count}")
        event_index = self._dataset_event_plot_indices_cache.get(
            id(self.rtdc_ds.hparent), 0)
        self.ui.spinBox_event.setValue(event_index + 1)
        self.ui.spinBox_event.blockSignals(False)

        # set quick view state
        self.write_pipeline_state(state)
        # scatter plot
        self.plot()
        try:
            self.show_event(event_index)
        except IndexError:
            self.show_event(0)

        # this only updates the size of the tools (because there is no
        # sender)
        self.on_tool()

    def show_statistics(self):
        h, v = self.get_statistics()
        if h is not None:
            self.ui.tableWidget_stat.set_key_vals(keys=h, vals=v)

    def update_feature_choices(self):
        """Updates the axes comboboxes choices

        This is used e.g. when emodulus becomes available
        """
        if self.rtdc_ds is not None:
            # axes combobox choices
            self.ui.comboBox_x.update_feature_list()
            self.ui.comboBox_y.update_feature_list()
            self.ui.comboBox_z_hue.update_feature_list()

    @QtCore.pyqtSlot()
    def update_polygon_panel(self):
        """Update polygon filter combobox etc."""
        if self.ui.label_poly_modify.isVisible():
            # User is currently modifying a polygon filter (issue 148).
            # We discard the user's changes.
            self.on_poly_done_cancel()

        pfts = dclab.PolygonFilter.instances
        self.ui.comboBox_poly.blockSignals(True)
        self.ui.comboBox_poly.clear()
        self.ui.comboBox_poly.addItem("Choose...", None)
        for pf in pfts:
            self.ui.comboBox_poly.addItem(pf.name, pf.unique_id)
        self.ui.comboBox_poly.blockSignals(False)
        self.ui.comboBox_poly.setEnabled(True)
        if not pfts:
            # disable combo box if there are no filters
            self.ui.comboBox_poly.setEnabled(False)
        self.ui.groupBox_poly.setEnabled(False)
