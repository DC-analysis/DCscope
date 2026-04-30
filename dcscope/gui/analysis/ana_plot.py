import logging

import dclab
import dclab.kde.binning
import dclab.kde.methods
import dclab.kde.smooth_contour
import numpy as np
from PyQt6 import QtCore, QtWidgets

from ...pipeline.plot import STATE_OPTIONS
from ..widgets import show_wait_cursor
from .ana_plot_ui import Ui_Form


COLORMAPS = STATE_OPTIONS["scatter"]["colormap"]

logger = logging.getLogger(__name__)


class PlotPanel(QtWidgets.QWidget):
    # widgets emit these whenever they changed the pipeline
    pp_mod_send = QtCore.pyqtSignal(dict)
    # widgets receive these so they can reflect the pipeline changes
    pp_mod_recv = QtCore.pyqtSignal(dict)

    def __init__(self, *args, **kwargs):
        super(PlotPanel, self).__init__(*args, **kwargs)

        self.ui = Ui_Form()
        self.ui.setupUi(self)

        # current DCscope pipeline
        self.pipeline = None
        self._init_controls()
        self.update_content()

        # options for division
        self.ui.comboBox_division.clear()
        self.ui.comboBox_division.addItem("Merge all plots", "merge")
        self.ui.comboBox_division.addItem("One plot per dataset", "each")
        self.ui.comboBox_division.addItem(
            "Scatter plots and joint contour plot",
            "multiscatter+contour")
        self.ui.comboBox_division.addItem("Only contour plots", "onlycontours")
        self.ui.comboBox_division.setCurrentIndex(2)

        # signals
        self.ui.toolButton_duplicate.clicked.connect(self.on_plot_duplicated)
        self.ui.toolButton_remove.clicked.connect(self.on_plot_removed)
        self.ui.pushButton_reset.clicked.connect(self.update_content)
        self.ui.pushButton_apply.clicked.connect(self.write_plot)
        self.ui.comboBox_plots.currentIndexChanged.connect(self.update_content)
        self.ui.comboBox_marker_hue.currentIndexChanged.connect(
            self.on_hue_selected)
        self.ui.comboBox_marker_feature.currentIndexChanged.connect(
            self.on_hue_selected)
        self.ui.comboBox_axis_x.currentIndexChanged.connect(
            self.on_axis_changed)
        self.ui.comboBox_axis_y.currentIndexChanged.connect(
            self.on_axis_changed)
        self.ui.comboBox_scale_x.currentIndexChanged.connect(
            self.on_axis_changed)
        self.ui.comboBox_scale_y.currentIndexChanged.connect(
            self.on_axis_changed)
        self.ui.spinBox_column_count.valueChanged.connect(
            self.on_column_num_changed)
        self.ui.widget_range_x.range_changed.connect(self.on_range_changed)
        self.ui.widget_range_y.range_changed.connect(self.on_range_changed)
        # automatically set spacing
        self.ui.toolButton_spacing_auto.clicked.connect(self.on_spacing_auto)

        self.pp_mod_recv.connect(self.on_pp_mod_recv)

    def read_plot_state(self):
        rx = self.ui.widget_range_x.read_pipeline_state()
        ry = self.ui.widget_range_y.read_pipeline_state()

        # hue min/max
        marker_hue = self.ui.comboBox_marker_hue.currentData()
        if marker_hue == "kde":
            hmin = 0
            hmax = 1
        elif marker_hue == "feature":
            rstate = self.ui.widget_range_feat.read_pipeline_state()
            hmin = rstate["start"]
            hmax = rstate["end"]
        else:
            hmin = hmax = np.nan

        state = {
            "identifier": self.current_plot.identifier,
            "layout": {
                "column count": self.ui.spinBox_column_count.value(),
                "division": self.ui.comboBox_division.currentData(),
                "label plots": self.ui.checkBox_label_plots.isChecked(),
                "name": self.ui.lineEdit.text(),
                "size x": self.ui.spinBox_size_x.value(),
                "size y": self.ui.spinBox_size_y.value(),
            },
            "general": {
                "auto range": self.ui.checkBox_auto_range.isChecked(),
                "axis x": self.ui.comboBox_axis_x.currentData(),
                "axis y": self.ui.comboBox_axis_y.currentData(),
                "isoelastics": self.ui.checkBox_isoelastics.isChecked(),
                "lut": self.ui.comboBox_lut.currentData(),
                "kde": self.ui.comboBox_kde.currentData(),
                "range x": [rx["start"], rx["end"]],
                "range y": [ry["start"], ry["end"]],
                "scale x": self.ui.comboBox_scale_x.currentData(),
                "scale y": self.ui.comboBox_scale_y.currentData(),
                "spacing x": self.ui.doubleSpinBox_spacing_x.value(),
                "spacing y": self.ui.doubleSpinBox_spacing_y.value(),
            },
            "scatter": {
                "colormap": self.ui.comboBox_colormap.currentData(),
                "downsample": self.ui.checkBox_downsample.isChecked(),
                "downsampling value": self.ui.spinBox_downsample.value(),
                "enabled": self.ui.groupBox_scatter.isChecked(),
                "hue feature": self.ui.comboBox_marker_feature.currentData(),
                "hue max": hmax,
                "hue min": hmin,
                "marker alpha": self.ui.spinBox_alpha.value() / 100,
                "marker hue": marker_hue,
                "marker size": self.ui.doubleSpinBox_marker_size.value(),
                "show event count": self.ui.checkBox_event_count.isChecked(),
            },
            "contour": {
                "enabled": self.ui.groupBox_contour.isChecked(),
                "legend":  self.ui.checkBox_legend.isChecked(),
                "zoomin":  self.ui.checkBox_zoomin.isChecked(),
                "line widths": [self.ui.doubleSpinBox_lw_1.value(),
                                self.ui.doubleSpinBox_lw_2.value(),
                                ],
                "line styles": [self.ui.comboBox_ls_1.currentData(),
                                self.ui.comboBox_ls_2.currentData(),
                                ],
                "percentiles": [self.ui.doubleSpinBox_perc_1.value(),
                                self.ui.doubleSpinBox_perc_2.value(),
                                ],
            }
        }
        return state

    def write_plot_state(self, state):
        if self.current_plot.identifier != state["identifier"]:
            raise ValueError("Plot identifier mismatch!")
        toblock = [
            self.ui.comboBox_axis_x,
            self.ui.comboBox_axis_y,
            self.ui.widget_range_x,
            self.ui.widget_range_y,
            self.ui.comboBox_marker_hue,
        ]

        for b in toblock:
            b.blockSignals(True)

        # Layout
        lay = state["layout"]
        self.ui.spinBox_column_count.setValue(lay["column count"])
        idx = self.ui.comboBox_division.findData(lay["division"])
        self.ui.comboBox_division.setCurrentIndex(idx)
        self.ui.checkBox_label_plots.setChecked(lay["label plots"])
        self.ui.lineEdit.setText(lay["name"])
        self.ui.spinBox_size_x.setValue(lay["size x"])
        self.ui.spinBox_size_y.setValue(lay["size y"])
        # General
        gen = state["general"]
        self.ui.checkBox_auto_range.setChecked(gen["auto range"])
        self.ui.comboBox_axis_x.setCurrentIndex(
            self.ui.comboBox_axis_x.findData(gen["axis x"]))
        self.ui.comboBox_axis_y.setCurrentIndex(
            self.ui.comboBox_axis_y.findData(gen["axis y"]))
        self.ui.checkBox_isoelastics.setChecked(gen["isoelastics"])
        lut_index = self.ui.comboBox_lut.findData(
            gen.get("lut", "LE-2D-FEM-19"))
        self.ui.comboBox_lut.setCurrentIndex(lut_index)
        kde_index = self.ui.comboBox_kde.findData(gen["kde"])
        self.ui.comboBox_kde.setCurrentIndex(kde_index)
        scx_index = self.ui.comboBox_scale_x.findData(gen["scale x"])
        self.ui.comboBox_scale_x.setCurrentIndex(scx_index)
        scy_index = self.ui.comboBox_scale_y.findData(gen["scale y"])
        self.ui.comboBox_scale_y.setCurrentIndex(scy_index)
        self._set_range_xy_state(axis_x=gen["axis x"],
                                 axis_y=gen["axis y"],
                                 range_x=gen["range x"],
                                 range_y=gen["range y"],
                                 )

        # Scatter
        sca = state["scatter"]
        self.ui.checkBox_downsample.setChecked(sca["downsample"])
        self.ui.spinBox_downsample.setValue(sca["downsampling value"])
        self.ui.groupBox_scatter.setChecked(sca["enabled"])
        hue_index = self.ui.comboBox_marker_hue.findData(sca["marker hue"])
        self.ui.comboBox_marker_hue.setCurrentIndex(hue_index)
        self.ui.doubleSpinBox_marker_size.setValue(sca["marker size"])
        feat_index = self.ui.comboBox_marker_feature.findData(
            sca["hue feature"])
        feat_index = feat_index or 0
        self.ui.comboBox_marker_feature.setCurrentIndex(feat_index)
        color_index = COLORMAPS.index(sca["colormap"])
        self.ui.comboBox_colormap.setCurrentIndex(color_index)
        self.ui.checkBox_event_count.setChecked(sca["show event count"])
        self.ui.spinBox_alpha.setValue(int(sca["marker alpha"]*100))
        if sca["marker hue"] == "feature":
            self._set_range_feat_state(sca["hue feature"], sca["hue min"],
                                       sca["hue max"])

        # Contour
        con = state["contour"]
        self.ui.groupBox_contour.setChecked(con["enabled"])
        self.ui.checkBox_legend.setChecked(con["legend"])
        self.ui.doubleSpinBox_perc_1.setValue(con["percentiles"][0])
        self.ui.doubleSpinBox_perc_2.setValue(con["percentiles"][1])
        self.ui.doubleSpinBox_lw_1.setValue(con["line widths"][0])
        self.ui.doubleSpinBox_lw_2.setValue(con["line widths"][1])
        ls1_index = self.ui.comboBox_ls_1.findData(con["line styles"][0])
        self.ui.comboBox_ls_1.setCurrentIndex(ls1_index)
        ls2_index = self.ui.comboBox_ls_2.findData(con["line styles"][1])
        self.ui.comboBox_ls_2.setCurrentIndex(ls2_index)
        self._set_kde_spacing(spacing_x=gen["spacing x"],
                              spacing_y=gen["spacing y"])
        for b in toblock:
            b.blockSignals(False)

    def _init_controls(self):
        """All controls that are not subject to change"""
        # LUT
        self.ui.comboBox_lut.clear()
        lut_dict = dclab.features.emodulus.load.get_internal_lut_names_dict()
        for lut_id in lut_dict.keys():
            self.ui.comboBox_lut.addItem(lut_id, lut_id)
        # KDE
        kde_names = STATE_OPTIONS["general"]["kde"]
        self.ui.comboBox_kde.clear()
        for kn in kde_names:
            self.ui.comboBox_kde.addItem(kn.capitalize(), kn)
        # Scales
        scales = STATE_OPTIONS["general"]["scale x"]
        self.ui.comboBox_scale_x.clear()
        self.ui.comboBox_scale_y.clear()
        for sc in scales:
            if sc == "log":
                vc = "logarithmic"
            else:
                vc = sc
            self.ui.comboBox_scale_x.addItem(vc, sc)
            self.ui.comboBox_scale_y.addItem(vc, sc)
        # Marker hue
        hues = STATE_OPTIONS["scatter"]["marker hue"]
        self.ui.comboBox_marker_hue.clear()
        for hue in hues:
            if hue == "kde":
                huev = "KDE"
            else:
                huev = hue.capitalize()
            self.ui.comboBox_marker_hue.addItem(huev, hue)
        self.ui.comboBox_colormap.clear()
        for c in COLORMAPS:
            self.ui.comboBox_colormap.addItem(c, c)
        # Contour line styles
        lstyles = STATE_OPTIONS["contour"]["line styles"][0]
        self.ui.comboBox_ls_1.clear()
        self.ui.comboBox_ls_2.clear()
        for ls in lstyles:
            self.ui.comboBox_ls_1.addItem(ls, ls)
            self.ui.comboBox_ls_2.addItem(ls, ls)
        # range controls
        for rc in [self.ui.widget_range_x, self.ui.widget_range_y,
                   self.ui.widget_range_feat]:
            rc.setLabel("")
            rc.setCheckable(False)
        # hide feature label range selection
        self.ui.widget_range_feat.hide()

    def _set_range_feat_state(self, feat, fmin=None, fmax=None):
        """Set a proper state for the feature hue range control"""
        if len(self.pipeline.slots) == 0:
            self.setEnabled(False)
            # do nothing
            return
        else:
            self.setEnabled(True)
        if feat is not None:
            lim = self.pipeline.get_min_max_coarse(
                feat=feat, plot_id=self.current_plot.identifier)
            if not (np.isinf(lim[0]) or np.isinf(lim[1])):
                self.ui.widget_range_feat.setLimits(vmin=lim[0], vmax=lim[1])
                if fmin is None:
                    fmin = lim[0]
                if fmax is None:
                    fmax = lim[1]
                new_state = {"active": True,
                             "start": fmin,
                             "end": fmax,
                             }
                self.ui.widget_range_feat.write_pipeline_state(new_state)

    def _set_range_xy_state(self, axis_x=None, range_x=None,
                            axis_y=None, range_y=None):
        """Set a proper state for the x/y range controls"""
        if len(self.pipeline.slots) == 0:
            self.setEnabled(False)
            # do nothing
            return
        else:
            self.setEnabled(True)

        plot_id = self.current_plot.identifier

        for axis, rang, rc in zip(
            [axis_x, axis_y],
            [range_x, range_y],
            [self.ui.widget_range_x, self.ui.widget_range_y],
        ):
            if axis is not None:
                lim = self.pipeline.get_min_max_coarse(
                    feat=axis,
                    plot_id=plot_id)
                if not (np.isinf(lim[0]) or np.isinf(lim[1])):
                    rc.blockSignals(True)
                    rc.setLimits(vmin=lim[0],
                                 vmax=lim[1])
                    if rang is None or rang[0] == rang[1]:
                        # default range is limits + 5% margin
                        rang = self.pipeline.get_min_max_coarse(
                            feat=axis,
                            plot_id=plot_id,
                            margin=0.05)
                    rc.write_pipeline_state({"active": True,
                                             "start": rang[0],
                                             "end": rang[1],
                                             })
                    rc.blockSignals(False)

    def _set_kde_spacing(self, spacing_x=None, spacing_y=None):
        """Set the KDE spacing in the spin boxes

        - sets spinbox limits first
        - sets number of digits
        - sets step
        - sets value in the end
        """
        for spacing, spinBox in zip([spacing_x, spacing_y],
                                    [self.ui.doubleSpinBox_spacing_x,
                                     self.ui.doubleSpinBox_spacing_y]):
            if spacing is None or np.isnan(spacing) or spacing == 0:
                continue
            else:
                if spacing >= 1:
                    dec = 2
                else:
                    dec = -int(np.log10(spacing)) + 3
                spinBox.setDecimals(dec)
                spinBox.setMinimum(10**-dec)
                spinBox.setMaximum(max(10*spacing, 10))
                spinBox.setSingleStep(10**(-dec + 1))
                spinBox.setValue(spacing)

    def _set_kde_spacing_simple(self, axis_x=None, axis_y=None):
        """automatically estimate and set the KDE spacing

        Not to be confused with `on_spacing_auto`!
        """
        if len(self.pipeline.slots) == 0:
            self.setEnabled(False)
            # do nothing
            return
        else:
            self.setEnabled(True)

        spacings_xy = []
        for feat, scaleCombo in zip([axis_x, axis_y],
                                    [self.ui.comboBox_scale_x,
                                     self.ui.comboBox_scale_y]):
            if feat is None:
                spacings_xy.append(None)
            else:
                vmin, vmax = self.pipeline.get_min_max_coarse(
                    feat=feat,
                    plot_id=self.current_plot.identifier)

                if scaleCombo.currentData() == "log":
                    vmin = np.log(vmin)
                    vmax = np.log(vmax)

                spacings_xy.append((vmax-vmin)/300)

        spacing_x, spacing_y = spacings_xy
        # sets the limits before setting the value
        self._set_kde_spacing(spacing_x=spacing_x,
                              spacing_y=spacing_y)

    @property
    def current_plot(self):
        if self.plot_ids:
            plot_index = self.ui.comboBox_plots.currentIndex()
            plot = self.pipeline.plots[plot_index]
        else:
            plot = None
        return plot

    @property
    def plot_ids(self):
        """List of plot identifiers"""
        if self.pipeline is not None:
            ids = [plot.identifier for plot in self.pipeline.plots]
        else:
            ids = []
        return ids

    @property
    def plot_names(self):
        """List of plot names"""
        if self.pipeline is not None:
            ids = [plot.name for plot in self.pipeline.plots]
        else:
            ids = []
        return ids

    def get_features(self):
        """Wrapper around pipeline with default features if empty"""
        feats_srt = self.pipeline.get_features(
            scalar=True, label_sort=True, plot_id=self.current_plot.identifier)
        if len(feats_srt) == 0:
            # fallback (nothing in the pipeline)
            features = dclab.dfn.scalar_feature_names
            labs = [dclab.dfn.get_feature_label(f) for f in features]
            lf = sorted(zip(labs, features))
            feats_srt = [it[1] for it in lf]
        return feats_srt

    @QtCore.pyqtSlot()
    def on_axis_changed(self):
        gen = self.read_plot_state()["general"]
        if self.sender() == self.ui.comboBox_axis_x:
            self._set_range_xy_state(axis_x=gen["axis x"])
            self._set_kde_spacing_simple(axis_x=gen["axis x"])
        elif self.sender() == self.ui.comboBox_axis_y:
            self._set_range_xy_state(axis_y=gen["axis y"])
            self._set_kde_spacing_simple(axis_y=gen["axis y"])
        elif self.sender() == self.ui.comboBox_scale_x:
            self._set_kde_spacing_simple(axis_x=gen["axis x"])
        elif self.sender() == self.ui.comboBox_scale_y:
            self._set_kde_spacing_simple(axis_y=gen["axis y"])

    @QtCore.pyqtSlot()
    def on_column_num_changed(self):
        """The user changed the number of columns

        - increase/decrease self.ui.spinBox_size_x by 150pt
        - increase/decrease self.ui.spinBox_size_y by 150pt if
          the row count changes as well
        """
        # old parameters
        state = self.current_plot.__getstate__()
        plot_id = state["identifier"]
        plot_index = self.pipeline.plot_ids.index(plot_id)
        old_size_x = state["layout"]["size x"]
        old_size_y = state["layout"]["size y"]
        old_ncol, old_nrow = self.pipeline.get_plot_col_row_count(plot_id)
        # new parameters
        new_pipeline_state = self.pipeline.__getstate__()
        new_pipeline_state["plots"][plot_index] = self.read_plot_state()
        new_ncol, new_nrow = self.pipeline.get_plot_col_row_count(
            plot_id, new_pipeline_state)
        # size x (minimum of 400)
        new_size_x = max(400, old_size_x + 200*(new_ncol - old_ncol))
        self.ui.spinBox_size_x.setValue(new_size_x)
        # size y
        new_size_y = max(400, old_size_y + 200*(new_nrow - old_nrow))
        self.ui.spinBox_size_y.setValue(new_size_y)

    @QtCore.pyqtSlot()
    def on_hue_selected(self):
        """Show/hide options for feature-based hue selection"""
        selection = self.ui.comboBox_marker_hue.currentData()
        # hide everything
        self.ui.comboBox_marker_feature.hide()
        self.ui.widget_dataset_alpha.hide()
        self.ui.comboBox_colormap.hide()
        self.ui.label_colormap.hide()
        self.ui.widget_range_feat.hide()
        # Only show feature selection if needed
        if selection == "feature":
            self.ui.comboBox_marker_feature.show()
            self.ui.comboBox_colormap.show()
            self.ui.label_colormap.show()
            self.ui.widget_range_feat.show()
            # set the range
            self._set_range_feat_state(
                feat=self.ui.comboBox_marker_feature.currentData())
        elif selection == "kde":
            self.ui.comboBox_colormap.show()
            self.ui.label_colormap.show()
        elif selection in ["dataset", "none"]:
            self.ui.widget_dataset_alpha.show()
        else:
            raise ValueError("Unknown selection: '{}'".format(selection))

    @QtCore.pyqtSlot()
    def on_plot_duplicated(self):
        with self.pipeline.lock:
            plot_id = self.current_plot.identifier
            new_id = self.pipeline.duplicate_plot(plot_id)
        self.pp_mod_send.emit({"pipeline": {"plot_created": new_id}})

    @QtCore.pyqtSlot()
    def on_plot_removed(self):
        with self.pipeline.lock:
            plot_id = self.current_plot.identifier
            self.pipeline.remove_plot(plot_id)
        self.pp_mod_send.emit({"pipeline": {"plot_removed": plot_id}})

    @QtCore.pyqtSlot(dict)
    def on_pp_mod_recv(self, data):
        """We received a signal that something changed"""
        if self.isVisible():
            pp_dict = data.get("pipeline", {})
            if "plot_added" in pp_dict:
                plot_id = pp_dict.get("plot_added")
                if plot_id is not None:
                    plot_index = self.pipeline.plot_ids.index(plot_id)
                else:
                    plot_index = None
                self.update_content(plot_index)

            pr_dict = data.get("pipeline-rendering", {})
            if "plot_size_changed" in pr_dict:
                plot_id = pr_dict.get("plot_size_changed")
                plot_index = self.pipeline.plot_ids.index(plot_id)
                state = self.pipeline.plots[plot_index].__getstate__()
                self.ui.spinBox_size_x.setValue(state["layout"]["size x"])
                self.ui.spinBox_size_y.setValue(state["layout"]["size y"])
            elif "plot_range_corrected" in pr_dict:
                plot_id = pr_dict.get("plot_range_corrected")
                plot_index = self.pipeline.plot_ids.index(plot_id)
                state = self.pipeline.plots[plot_index].__getstate__()
                for nm, rc in [("range x", self.ui.widget_range_x),
                               ("range y", self.ui.widget_range_y)]:
                    rc.blockSignals(True)
                    rc.write_pipeline_state({
                        "active": True,
                        "start": state["general"][nm][0],
                        "end": state["general"][nm][1],
                    })
                    rc.blockSignals(False)

    @QtCore.pyqtSlot()
    @show_wait_cursor
    def on_spacing_auto(self):
        """Iteratively find a good spacing for smooth contours (#110)"""
        # https://github.com/DC-analysis/DCscope/issues/110
        plot_id = self.current_plot.identifier
        state = self.read_plot_state()

        # compute best spacing iteratively
        res = dclab.kde.smooth_contour.find_smooth_contour_spacing(
            # All datasets belonging to this plot.
            ds_list=self.pipeline.get_plot_datasets(plot_id)[0],
            xax=state["general"]["axis x"],
            yax=state["general"]["axis y"],
            xrange=state["general"]["range x"],
            yrange=state["general"]["range y"],
            quantiles=np.array(state["contour"]["percentiles"]) / 100,
            xscale=state["general"]["scale x"],
            yscale=state["general"]["scale y"],
            kde_type="histogram",
            max_iter=15,
        )

        success = res.get("success", False)
        reason = res.get("reason", "unknown")
        num_iter = res.get("total iterations", np.nan)
        corners_found = res.get("corners found", "unknown")

        if success:
            logger.info(
                f"Successfully found smooth contour within {num_iter} "
                f"iterations: {reason} ({corners_found=})."
            )
        else:
            logger.warning(
                f"Failed to find smooth contour within {num_iter} "
                f"iterations: {reason} ({corners_found=})."
            )

        # set the final spacing
        new_state = self.read_plot_state()
        new_state["general"]["spacing x"] = res["spacing x"]
        new_state["general"]["spacing y"] = res["spacing y"]
        self.write_plot_state(new_state)

    @QtCore.pyqtSlot()
    def on_range_changed(self):
        """User changed x/y range -> disable auto range checkbox"""
        self.ui.checkBox_auto_range.setChecked(False)

    def show_plot(self, plot_id):
        self.update_content(plot_index=self.plot_ids.index(plot_id))

    def set_pipeline(self, pipeline):
        if self.pipeline is not None:
            raise ValueError("Pipeline can only be set once")
        self.pipeline = pipeline

    def update_content(self, plot_index=None, **kwargs):
        if self.plot_ids:
            # remember the previous plot index and make sure it is sane
            prev_index = self.ui.comboBox_plots.currentIndex()
            if prev_index is None or prev_index < 0:
                prev_index = len(self.plot_ids) - 1

            self.setEnabled(True)
            # update combobox
            self.ui.comboBox_plots.blockSignals(True)
            # this also updates the combobox
            if plot_index is None or plot_index < 0:
                plot_index = prev_index
            plot_index = min(plot_index, len(self.plot_ids) - 1)

            self.ui.comboBox_plots.clear()
            self.ui.comboBox_plots.addItems(self.plot_names)
            self.ui.comboBox_plots.setCurrentIndex(plot_index)
            self.ui.comboBox_plots.blockSignals(False)
            # set choices for all comboboxes that deal with features
            for cb in [self.ui.comboBox_axis_x,
                       self.ui.comboBox_axis_y,
                       self.ui.comboBox_marker_feature]:
                # get the features currently available
                feats_srt = self.get_features()
                cb.blockSignals(True)
                # remember previous selection if possible
                if cb.count:
                    # remember current selection
                    curfeat = cb.currentData()
                    if curfeat not in feats_srt:
                        curfeat = None
                else:
                    curfeat = None
                # repopulate
                cb.clear()
                for feat in feats_srt:
                    cb.addItem(dclab.dfn.get_feature_label(feat), feat)
                if curfeat is not None:
                    # write back current selection
                    curidx = cb.findData(curfeat)
                    cb.setCurrentIndex(curidx)
                cb.blockSignals(False)
            # populate content
            plot = self.pipeline.plots[plot_index]
            state = plot.__getstate__()
            self.write_plot_state(state)
        else:
            self.setEnabled(False)

    @QtCore.pyqtSlot()
    def write_plot(self):
        """Update the dcscope.pipeline.Plot instance"""
        with self.pipeline.lock:
            # get current index
            plot_state = self.read_plot_state()
            plot_id = plot_state["identifier"]
            plot_index = self.pipeline.plot_ids.index(plot_id)
            self.pipeline.plots[plot_index].__setstate__(plot_state)
        self.pp_mod_send.emit({"pipeline": {"plot_changed": plot_id}})
