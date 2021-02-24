import copy
import pkg_resources

import dclab
import numpy as np
from PyQt5 import uic, QtCore, QtWidgets

from ...pipeline import Plot
from ...pipeline.plot import STATE_OPTIONS


COLORMAPS = STATE_OPTIONS["scatter"]["colormap"]


class PlotPanel(QtWidgets.QWidget):
    #: Emitted when a shapeout2.pipeline.Plot is to be changed
    plot_changed = QtCore.pyqtSignal(dict)
    #: Emitted when the pipeline is to be changed
    pipeline_changed = QtCore.pyqtSignal(dict)

    def __init__(self, *args, **kwargs):
        QtWidgets.QWidget.__init__(self)
        path_ui = pkg_resources.resource_filename(
            "shapeout2.gui.analysis", "ana_plot.ui")
        uic.loadUi(path_ui, self)

        # current Shape-Out 2 pipeline
        self._pipeline = None
        self._init_controls()
        self.update_content()

        # options for division
        self.comboBox_division.clear()
        self.comboBox_division.addItem("Merge all plots", "merge")
        self.comboBox_division.addItem("One plot per dataset", "each")
        self.comboBox_division.addItem("Scatter plots and joint contour plot",
                                       "multiscatter+contour")
        self.comboBox_division.setCurrentIndex(2)

        # signals
        self.toolButton_duplicate.clicked.connect(self.on_plot_duplicated)
        self.toolButton_remove.clicked.connect(self.on_plot_removed)
        self.pushButton_reset.clicked.connect(self.update_content)
        self.pushButton_apply.clicked.connect(self.write_plot)
        self.comboBox_plots.currentIndexChanged.connect(self.update_content)
        self.comboBox_marker_hue.currentIndexChanged.connect(
            self.on_hue_selected)
        self.comboBox_marker_feature.currentIndexChanged.connect(
            self.on_hue_selected)
        self.comboBox_axis_x.currentIndexChanged.connect(self.on_axis_changed)
        self.comboBox_axis_y.currentIndexChanged.connect(self.on_axis_changed)
        self.comboBox_scale_x.currentIndexChanged.connect(self.on_axis_changed)
        self.comboBox_scale_y.currentIndexChanged.connect(self.on_axis_changed)
        self.spinBox_column_count.valueChanged.connect(
            self.on_column_num_changed)
        self.widget_range_x.range_changed.connect(self.on_range_changed)
        self.widget_range_y.range_changed.connect(self.on_range_changed)

    def __getstate__(self):
        feats_srt = self.get_features()

        rx = self.widget_range_x.__getstate__()
        ry = self.widget_range_y.__getstate__()

        # hue min/max
        marker_hue = self.comboBox_marker_hue.currentData()
        if marker_hue == "kde":
            hmin = 0
            hmax = 1
        elif marker_hue == "feature":
            rstate = self.widget_range_feat.__getstate__()
            hmin = rstate["start"]
            hmax = rstate["end"]
        else:
            hmin = hmax = np.nan

        state = {
            "identifier": self.current_plot.identifier,
            "layout": {
                "column count": self.spinBox_column_count.value(),
                "division": self.comboBox_division.currentData(),
                "label plots": self.checkBox_label_plots.isChecked(),
                "name": self.lineEdit.text(),
                "size x": self.spinBox_size_x.value(),
                "size y": self.spinBox_size_y.value(),
            },
            "general": {
                "auto range": self.checkBox_auto_range.isChecked(),
                "axis x": feats_srt[self.comboBox_axis_x.currentIndex()],
                "axis y": feats_srt[self.comboBox_axis_y.currentIndex()],
                "isoelastics": self.checkBox_isoelastics.isChecked(),
                "kde": self.comboBox_kde.currentData(),
                "range x": [rx["start"], rx["end"]],
                "range y": [ry["start"], ry["end"]],
                "scale x": self.comboBox_scale_x.currentData(),
                "scale y": self.comboBox_scale_y.currentData(),
            },
            "scatter": {
                "colormap": self.comboBox_colormap.currentData(),
                "downsample": self.checkBox_downsample.isChecked(),
                "downsampling value": self.spinBox_downsample.value(),
                "enabled": self.groupBox_scatter.isChecked(),
                "hue feature": self.comboBox_marker_feature.currentData(),
                "hue max": hmax,
                "hue min": hmin,
                "marker alpha": self.spinBox_alpha.value() / 100,
                "marker hue": marker_hue,
                "marker size": self.doubleSpinBox_marker_size.value(),
                "show event count": self.checkBox_event_count.isChecked(),
            },
            "contour": {
                "enabled": self.groupBox_contour.isChecked(),
                "legend":  self.checkBox_legend.isChecked(),
                "line widths": [self.doubleSpinBox_lw_1.value(),
                                self.doubleSpinBox_lw_2.value(),
                                ],
                "line styles": [self.comboBox_ls_1.currentData(),
                                self.comboBox_ls_2.currentData(),
                                ],
                "percentiles": [self.doubleSpinBox_perc_1.value(),
                                self.doubleSpinBox_perc_2.value(),
                                ],
                "spacing x": self.doubleSpinBox_spacing_x.value(),
                "spacing y": self.doubleSpinBox_spacing_y.value(),
            }
        }
        return state

    def __setstate__(self, state):
        if self.current_plot.identifier != state["identifier"]:
            raise ValueError("Plot identifier mismatch!")
        feats_srt = self.get_features()
        toblock = [
            self.comboBox_axis_x,
            self.comboBox_axis_y,
            self.widget_range_x,
            self.widget_range_y,
        ]

        for b in toblock:
            b.blockSignals(True)

        # Layout
        lay = state["layout"]
        self.spinBox_column_count.setValue(lay["column count"])
        idx = self.comboBox_division.findData(lay["division"])
        self.comboBox_division.setCurrentIndex(idx)
        self.checkBox_label_plots.setChecked(lay["label plots"])
        self.lineEdit.setText(lay["name"])
        self.spinBox_size_x.setValue(lay["size x"])
        self.spinBox_size_y.setValue(lay["size y"])
        # General
        gen = state["general"]
        self.checkBox_auto_range.setChecked(gen["auto range"])
        self.comboBox_axis_x.setCurrentIndex(feats_srt.index(gen["axis x"]))
        self.comboBox_axis_y.setCurrentIndex(feats_srt.index(gen["axis y"]))
        self.checkBox_isoelastics.setChecked(gen["isoelastics"])
        kde_index = self.comboBox_kde.findData(gen["kde"])
        self.comboBox_kde.setCurrentIndex(kde_index)
        scx_index = self.comboBox_scale_x.findData(gen["scale x"])
        self.comboBox_scale_x.setCurrentIndex(scx_index)
        scy_index = self.comboBox_scale_y.findData(gen["scale y"])
        self.comboBox_scale_y.setCurrentIndex(scy_index)
        self._set_range_xy_state(axis_x=gen["axis x"],
                                 axis_y=gen["axis y"],
                                 range_x=gen["range x"],
                                 range_y=gen["range y"],
                                 )

        # Scatter
        sca = state["scatter"]
        self.checkBox_downsample.setChecked(sca["downsample"])
        self.spinBox_downsample.setValue(sca["downsampling value"])
        self.groupBox_scatter.setChecked(sca["enabled"])
        hue_index = self.comboBox_marker_hue.findData(sca["marker hue"])
        self.comboBox_marker_hue.setCurrentIndex(hue_index)
        self.doubleSpinBox_marker_size.setValue(sca["marker size"])
        if sca["hue feature"] in feats_srt:
            feat_index = feats_srt.index(sca["hue feature"])
        else:
            feat_index = 0  # feature not available in datasets
        self.comboBox_marker_feature.setCurrentIndex(feat_index)
        color_index = COLORMAPS.index(sca["colormap"])
        self.comboBox_colormap.setCurrentIndex(color_index)
        self.checkBox_event_count.setChecked(sca["show event count"])
        self.spinBox_alpha.setValue(int(sca["marker alpha"]*100))
        if sca["marker hue"] == "feature":
            self._set_range_feat_state(sca["hue feature"], sca["hue min"],
                                       sca["hue max"])

        # Contour
        con = state["contour"]
        self.groupBox_contour.setChecked(con["enabled"])
        self.checkBox_legend.setChecked(con["legend"])
        self.doubleSpinBox_perc_1.setValue(con["percentiles"][0])
        self.doubleSpinBox_perc_2.setValue(con["percentiles"][1])
        self.doubleSpinBox_lw_1.setValue(con["line widths"][0])
        self.doubleSpinBox_lw_2.setValue(con["line widths"][1])
        ls1_index = self.comboBox_ls_1.findData(con["line styles"][0])
        self.comboBox_ls_1.setCurrentIndex(ls1_index)
        ls2_index = self.comboBox_ls_2.findData(con["line styles"][1])
        self.comboBox_ls_2.setCurrentIndex(ls2_index)
        self._set_contour_spacing(spacing_x=con["spacing x"],
                                  spacing_y=con["spacing y"])
        for b in toblock:
            b.blockSignals(False)

    def _init_controls(self):
        """All controls that are not subject to change"""
        # KDE
        kde_names = STATE_OPTIONS["general"]["kde"]
        self.comboBox_kde.clear()
        for kn in kde_names:
            self.comboBox_kde.addItem(kn.capitalize(), kn)
        # Scales
        scales = STATE_OPTIONS["general"]["scale x"]
        self.comboBox_scale_x.clear()
        self.comboBox_scale_y.clear()
        for sc in scales:
            if sc == "log":
                vc = "logarithmic"
            else:
                vc = sc
            self.comboBox_scale_x.addItem(vc, sc)
            self.comboBox_scale_y.addItem(vc, sc)
        # Marker hue
        hues = STATE_OPTIONS["scatter"]["marker hue"]
        self.comboBox_marker_hue.clear()
        for hue in hues:
            if hue == "kde":
                huev = "KDE"
            else:
                huev = hue.capitalize()
            self.comboBox_marker_hue.addItem(huev, hue)
        self.comboBox_colormap.clear()
        for c in COLORMAPS:
            self.comboBox_colormap.addItem(c, c)
        # Contour line styles
        lstyles = STATE_OPTIONS["contour"]["line styles"][0]
        self.comboBox_ls_1.clear()
        self.comboBox_ls_2.clear()
        for ls in lstyles:
            self.comboBox_ls_1.addItem(ls, ls)
            self.comboBox_ls_2.addItem(ls, ls)
        # range controls
        for rc in [self.widget_range_x, self.widget_range_y,
                   self.widget_range_feat]:
            rc.setLabel("")
            rc.setCheckable(False)
        # hide feature label range selection
        self.widget_range_feat.hide()

    def _set_range_feat_state(self, feat, fmin=None, fmax=None):
        """Set a proper state for the feature hue range control"""
        if len(self.pipeline.slots) == 0:
            self.setEnabled(False)
            # do nothing
            return
        else:
            self.setEnabled(True)
        if feat is not None:
            lim = self.pipeline.get_min_max(
                feat=feat, plot_id=self.current_plot.identifier)
            if not (np.isinf(lim[0]) or np.isinf(lim[1])):
                self.widget_range_feat.setLimits(vmin=lim[0], vmax=lim[1])
                if fmin is None:
                    fmin = lim[0]
                if fmax is None:
                    fmax = lim[1]
                self.widget_range_feat.__setstate__({"active": True,
                                                     "start": fmin,
                                                     "end": fmax,
                                                     })

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

        for axis, rang, rc in zip([axis_x, axis_y],
                                  [range_x, range_y],
                                  [self.widget_range_x, self.widget_range_y],
                                  ):
            if axis is not None:
                lim = self.pipeline.get_min_max(feat=axis, plot_id=plot_id)
                if not (np.isinf(lim[0]) or np.isinf(lim[1])):
                    rc.setLimits(vmin=lim[0],
                                 vmax=lim[1])
                    if rang is None or rang[0] == rang[1]:
                        # default range is limits + 5% margin
                        rang = self.pipeline.get_min_max(feat=axis,
                                                         plot_id=plot_id,
                                                         margin=0.05)
                    rc.__setstate__({"active": True,
                                     "start": rang[0],
                                     "end": rang[1],
                                     })

    def _set_contour_spacing(self, spacing_x=None, spacing_y=None):
        """Set the contour spacing in the spin boxes

        - sets spinbox limits first
        - sets number of digits
        - sets step
        - sets value in the end
        """
        for spacing, spinBox in zip([spacing_x, spacing_y],
                                    [self.doubleSpinBox_spacing_x,
                                     self.doubleSpinBox_spacing_y]):
            if spacing is None:
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

    def _set_contour_spacing_auto(self, axis_x=None, axis_y=None):
        """automatically set the contour spacing

        - uses :func:`dclab.kde_methods.bin_width_percentile`
        - uses _set_contour_spacing
        """
        if len(self.pipeline.slots) == 0:
            self.setEnabled(False)
            # do nothing
            return
        else:
            self.setEnabled(True)
        dslist, _ = self.pipeline.get_plot_datasets(
            self.current_plot.identifier)
        if dslist:
            spacings_xy = []
            for axis, scaleCombo in zip([axis_x, axis_y],
                                        [self.comboBox_scale_x,
                                         self.comboBox_scale_y]):
                if axis is None:
                    # nothing to do
                    spacings_xy.append(None)
                else:
                    # determine good approximation
                    spacings = []
                    for ds in dslist:
                        spa = ds.get_kde_spacing(
                            a=ds[axis],
                            feat=axis,
                            scale=scaleCombo.currentData(),
                            method=dclab.kde_methods.bin_width_percentile,
                        )
                        spacings.append(spa)
                    spacings_xy.append(np.min(spacings))
            spacing_x, spacing_y = spacings_xy
            # sets the limits before setting the value
            self._set_contour_spacing(spacing_x=spacing_x,
                                      spacing_y=spacing_y)

    @property
    def current_plot(self):
        if self.plot_ids:
            plot_index = self.comboBox_plots.currentIndex()
            plot_id = self.plot_ids[plot_index]
            plot = Plot.get_instances()[plot_id]
        else:
            plot = None
        return plot

    @property
    def pipeline(self):
        return self._pipeline

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

    def on_axis_changed(self):
        gen = self.__getstate__()["general"]
        if self.sender() == self.comboBox_axis_x:
            self._set_range_xy_state(axis_x=gen["axis x"])
            self._set_contour_spacing_auto(axis_x=gen["axis x"])
        elif self.sender() == self.comboBox_axis_y:
            self._set_range_xy_state(axis_y=gen["axis y"])
            self._set_contour_spacing_auto(axis_y=gen["axis y"])
        elif self.sender() == self.comboBox_scale_x:
            self._set_contour_spacing_auto(axis_x=gen["axis x"])
        elif self.sender() == self.comboBox_scale_y:
            self._set_contour_spacing_auto(axis_y=gen["axis y"])

    def on_column_num_changed(self):
        """The user changed the number of columns

        - increase/decrease self.spinBox_size_x by 150pt
        - increase/decrease self.spinBox_size_y by 150pt if
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
        new_pipeline_state["plots"][plot_index] = self.__getstate__()
        new_ncol, new_nrow = self.pipeline.get_plot_col_row_count(
            plot_id, new_pipeline_state)
        # size x (minimum of 400)
        new_size_x = max(400, old_size_x + 200*(new_ncol - old_ncol))
        self.spinBox_size_x.setValue(new_size_x)
        # size y
        new_size_y = max(400, old_size_y + 200*(new_nrow - old_nrow))
        self.spinBox_size_y.setValue(new_size_y)

    def on_hue_selected(self):
        """Show/hide options for feature-based hue selection"""
        selection = self.comboBox_marker_hue.currentData()
        # hide everything
        self.comboBox_marker_feature.hide()
        self.widget_dataset_alpha.hide()
        self.comboBox_colormap.hide()
        self.label_colormap.hide()
        self.widget_range_feat.hide()
        # Only show feature selection if needed
        if selection == "feature":
            self.comboBox_marker_feature.show()
            self.comboBox_colormap.show()
            self.label_colormap.show()
            self.widget_range_feat.show()
            # set the range
            self._set_range_feat_state(
                feat=self.comboBox_marker_feature.currentData())
        elif selection == "kde":
            self.comboBox_colormap.show()
            self.label_colormap.show()
        elif selection in ["dataset", "none"]:
            self.widget_dataset_alpha.show()
        else:
            raise ValueError("Unknown selection: '{}'".format(selection))

    def on_plot_duplicated(self):
        # determine the new filter state
        plot_state = self.__getstate__()
        new_state = copy.deepcopy(plot_state)
        new_plot = Plot()
        new_state["identifier"] = new_plot.identifier
        new_state["layout"]["name"] = new_plot.name
        new_plot.__setstate__(new_state)
        # determine the filter position
        pos = self.pipeline.plot_ids.index(plot_state["identifier"])
        self.pipeline.add_plot(new_plot, index=pos+1)
        state = self.pipeline.__getstate__()
        self.pipeline_changed.emit(state)

    def on_plot_removed(self):
        plot_state = self.__getstate__()
        self.pipeline.remove_plot(plot_state["identifier"])
        state = self.pipeline.__getstate__()
        self.pipeline_changed.emit(state)

    def on_range_changed(self):
        """User changed x/y range -> disable auto range checkbox"""
        self.checkBox_auto_range.setChecked(False)

    def show_plot(self, plot_id):
        self.update_content(plot_index=self.plot_ids.index(plot_id))

    def set_pipeline(self, pipeline):
        self._pipeline = pipeline

    def update_content(self, event=None, plot_index=None):
        if self.plot_ids:
            self.setEnabled(True)
            # update combobox
            self.comboBox_plots.blockSignals(True)
            # this also updates the combobox
            if plot_index is None:
                plot_index = self.comboBox_plots.currentIndex()
                if plot_index > len(self.plot_ids) - 1 or plot_index < 0:
                    plot_index = len(self.plot_ids) - 1
            self.comboBox_plots.clear()
            self.comboBox_plots.addItems(self.plot_names)
            self.comboBox_plots.setCurrentIndex(plot_index)
            self.comboBox_plots.blockSignals(False)
            # set choices for all comboboxes that deal with features
            for cb in [self.comboBox_axis_x,
                       self.comboBox_axis_y,
                       self.comboBox_marker_feature]:
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
                    curidx = feats_srt.index(curfeat)
                    cb.setCurrentIndex(curidx)
                cb.blockSignals(False)
            # populate content
            plot = Plot.get_plot(identifier=self.plot_ids[plot_index])
            state = plot.__getstate__()
            self.__setstate__(state)
        else:
            self.setEnabled(False)

    def write_plot(self):
        """Update the shapeout2.pipeline.Plot instance"""
        # get current index
        plot_index = self.comboBox_plots.currentIndex()
        plot = Plot.get_plot(identifier=self.plot_ids[plot_index])
        plot_state = self.__getstate__()
        plot.__setstate__(plot_state)
        self.update_content()  # update plot selection combobox
        self.plot_changed.emit(plot_state)
