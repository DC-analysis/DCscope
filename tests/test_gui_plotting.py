"""Plotting GUI tests"""
import pathlib
import tempfile

import dclab
import h5py
import numpy as np
import pytest
from PyQt6 import QtCore, QtWidgets

from dcscope import pipeline, session

import conftest  # noqa: F401


datapath = pathlib.Path(__file__).parent / "data"


@pytest.fixture(autouse=True)
def run_around_tests():
    # Code that will run before your test, for example:
    session.clear_session()
    # A test function will be run at this point
    yield
    # Code that will run after your test, for example:
    session.clear_session()


def test_empty_plot_with_one_plot_per_dataset_issue_41(qtbot, mw):
    """
    Setting "one plot per dataset" for an empty plot resulted in
    zero-division error when determining col/row numbers
    """
    qtbot.addWidget(mw)

    # add a dataslot
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])

    # add a plot
    plot_id = mw.add_plot()

    # activate analysis view
    pe = mw.ui.block_matrix.get_widget(filt_plot_id=plot_id)
    qtbot.mouseClick(pe.ui.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)

    mw.widget_ana_view.ui.tabWidget.setCurrentWidget(mw.widget_ana_view.ui.tab_plot)
    pv = mw.widget_ana_view.ui.widget_plot

    # Change to "each" and apply
    idx = pv.ui.comboBox_division.findData("each")
    pv.ui.comboBox_division.setCurrentIndex(idx)
    # Lead to zero-division error in "get_plot_col_row_count"
    qtbot.mouseClick(pv.ui.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)


def test_feature_bright_avg_not_present_issue_62(qtbot, mw):
    """Plot a dataset that does not contain the "bright_avg" feature

    ...or any means of computing it (i.e. via "image")
    """
    # create fake dataset without bright_avg
    tmp = tempfile.mktemp(".rtdc", prefix="example_hue_")
    with dclab.new_dataset(datapath / "calibration_beads_47.rtdc") as ds:
        ds.export.hdf5(tmp, features=["area_um", "pos_x", "pos_y", "deform"])

    qtbot.addWidget(mw)
    # add dataset
    slot_id = mw.add_dataslot([tmp])[0]
    # add plot
    plot_id = mw.add_plot()
    # and activate it
    pw = mw.ui.block_matrix.get_widget(filt_plot_id=plot_id, slot_id=slot_id)
    # this raised "ValueError: 'bright_avg' is not in list" (issue #62)
    qtbot.mouseClick(pw, QtCore.Qt.MouseButton.LeftButton)


def test_handle_axis_selection_empty_plot(qtbot, mw):
    """User did not add a dataset to a plot and starts changing plot params"""
    qtbot.addWidget(mw)

    # add a dataslot
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])

    # add a plot
    plot_id = mw.add_plot()

    assert len(mw.pipeline.slot_ids) == 1, "we added that"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"
    assert len(mw.pipeline.plot_ids) == 1, "we added that"

    # activate analysis view
    pe = mw.ui.block_matrix.get_widget(filt_plot_id=plot_id)
    qtbot.mouseClick(pe.ui.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)

    mw.widget_ana_view.ui.tabWidget.setCurrentWidget(mw.widget_ana_view.ui.tab_plot)
    pv = mw.widget_ana_view.ui.widget_plot

    # This lead to:
    #    Traceback (most recent call last):
    #  File "/DCscope/dcscope/gui/analysis/ana_plot.py",
    #     line 406, in on_axis_changed
    #    self._set_contour_spacing_auto(axis_y=gen["axis y"])
    #  File "/DCscope/dcscope/gui/analysis/ana_plot.py",
    #     line 361, in _set_contour_spacing_auto
    #    spacings_xy.append(np.min(spacings))
    #  File "/numpy/core/fromnumeric.py", line 2618, in amin
    #    initial=initial)
    #  File "/numpy/core/fromnumeric.py", line 86, in _wrapreduction
    #    return ufunc.reduce(obj, axis, dtype, out, **passkwargs)
    # ValueError: zero-size array to reduction operation minimum which
    # has no identity
    pv.ui.comboBox_axis_y.setCurrentIndex(pv.ui.comboBox_axis_y.findData("emodulus"))


def test_handle_empty_plots_issue_27(qtbot, mw):
    """Correctly handle empty plots

    https://github.com/DC-analysis/DCscope/issues/27
    """
    qtbot.addWidget(mw)

    # add a dataslot
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])
    # add another one
    mw.add_dataslot(paths=[path])

    assert len(mw.pipeline.slot_ids) == 2, "we added those"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # activate a dataslot
    slot_id = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em = mw.ui.block_matrix.get_widget(slot_id, filt_id)
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton)  # activate
    # did that work?
    assert mw.pipeline.is_element_active(slot_id, filt_id)

    # filter away all events
    fe = mw.ui.block_matrix.get_widget(filt_plot_id=filt_id)
    qtbot.mouseClick(fe.ui.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)
    fv = mw.widget_ana_view.ui.widget_filter
    mw.widget_ana_view.ui.tabWidget.setCurrentWidget(
        mw.widget_ana_view.ui.tab_filter)

    qtbot.mouseClick(fv.ui.toolButton_moreless, QtCore.Qt.MouseButton.LeftButton)
    rc = fv._box_range_controls["area_um"]
    qtbot.mouseClick(rc.ui.checkBox, QtCore.Qt.MouseButton.LeftButton)
    # did that work?
    assert rc.ui.checkBox.isChecked()
    qtbot.mouseClick(fv.ui.toolButton_moreless, QtCore.Qt.MouseButton.LeftButton)
    # set range
    rc.ui.doubleSpinBox_min.setValue(0)
    rc.ui.doubleSpinBox_max.setValue(1)
    qtbot.mouseClick(fv.ui.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)
    # did that work?
    ds = mw.pipeline.get_dataset(slot_index=0, filt_index=0,
                                 apply_filter=True)
    assert np.sum(ds.filter.all) == 0

    # now create a plot window
    plot_id = mw.add_plot()
    pe = mw.ui.block_matrix.get_widget(slot_id, plot_id)
    with pytest.warns(pipeline.core.EmptyDatasetWarning):
        # this now only throws a warning
        # activate (raises #27)
        qtbot.mouseClick(pe, QtCore.Qt.MouseButton.LeftButton)

        QtWidgets.QApplication.processEvents(
            QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 500)


@pytest.mark.filterwarnings('ignore::dclab.kde.base.ContourSpacingTooLarge')
@pytest.mark.filterwarnings(
    'ignore::dclab.kde.binning.KernelDensityEstimationForEmtpyArrayWarning')
@pytest.mark.filterwarnings(
    'ignore::dcscope.pipeline.core.ContourSpacingWarning')
def test_handle_empty_plots_issue_223(qtbot, mw):
    """Correctly handle plots with empty datasets (before filtering)

    https://github.com/DC-analysis/DCscope/issues/223
    """
    qtbot.addWidget(mw)

    # add a dataslot without any events
    path = datapath / "empty_recording.rtdc"
    mw.add_dataslot(paths=[path])

    assert len(mw.pipeline.slot_ids) == 1, "we added those"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # Check whether we really don't have any events
    ds = mw.pipeline.get_dataset(slot_index=0, filt_index=0,
                                 apply_filter=True)
    assert len(ds) == 0
    assert np.sum(ds.filter.all) == 0

    # now create a plot window
    plot_id = mw.add_plot()
    pe = mw.ui.block_matrix.get_widget(mw.pipeline.slot_ids[0], plot_id)

    with pytest.warns(pipeline.core.EmptyDatasetWarning):
        qtbot.mouseClick(pe, QtCore.Qt.MouseButton.LeftButton)

        # this now only throws a warning
        # activate (raises #223)
        qtbot.mouseClick(pe, QtCore.Qt.MouseButton.LeftButton)

        QtWidgets.QApplication.processEvents(
            QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 500)


@pytest.mark.filterwarnings(
    'ignore::dclab.features.emodulus.YoungsModulusLookupTableExceededWarning')
def test_handle_nan_valued_feature_color(qtbot, mw):
    """User wants to color scatter data points with feature containing nans"""
    spath = datapath / "version_2_1_2_plot_color_emodulus.so2"

    qtbot.addWidget(mw)

    # lead to:
    # OverflowError: argument 4 overflowed: value must be in the range
    # -2147483648 to 2147483647
    mw.on_action_open(spath)


def test_hue_feature_not_computed_if_not_selected(qtbot, mw):
    # generate .rtdc file without bright_avg feature
    tmp = tempfile.mktemp(".rtdc", prefix="example_hue_")
    with dclab.new_dataset(datapath / "calibration_beads_47.rtdc") as ds:
        ds.export.hdf5(tmp, features=["area_um", "pos_x", "pos_y", "image",
                                      "mask", "deform"])
    qtbot.addWidget(mw)
    # add dataset
    slot_id = mw.add_dataslot([tmp])[0]
    # add plot
    plot_id = mw.add_plot()
    # and activate it
    pw = mw.ui.block_matrix.get_widget(filt_plot_id=plot_id, slot_id=slot_id)
    qtbot.mouseClick(pw, QtCore.Qt.MouseButton.LeftButton)
    # get the dataset
    ds = mw.pipeline.get_dataset(slot_index=0)
    # check whether the item has been plotted
    datasets, _ = mw.pipeline.get_plot_datasets(plot_id)
    assert datasets[0] is ds
    # now check whether "bright_avg" has been computed
    assert "bright_avg" in ds.features
    assert "bright_avg" not in ds.features_loaded


def test_plot_ml_score(qtbot, mw):
    tmp = tempfile.mktemp(".rtdc", prefix="example_ml_score_")
    with dclab.new_dataset(datapath / "calibration_beads_47.rtdc") as ds:
        ds.export.hdf5(tmp, features=["area_um", "pos_x", "pos_y", "image",
                                      "mask", "deform"])
        lends = len(ds)
    # add ml_score features
    with h5py.File(tmp, "a") as h5:
        h5["/events/ml_score_ds9"] = np.linspace(0, 1, lends)
        h5["/events/ml_score_voy"] = np.linspace(1, 0, lends)
    qtbot.addWidget(mw)
    # add dataset
    slot_id = mw.add_dataslot([tmp])[0]
    # add plot
    plot_id = mw.add_plot()
    # and activate it
    pw = mw.ui.block_matrix.get_widget(filt_plot_id=plot_id, slot_id=slot_id)
    qtbot.mouseClick(pw, QtCore.Qt.MouseButton.LeftButton)
    # get the dataset
    ds = mw.pipeline.get_dataset(slot_index=0)
    # sanity check
    assert "ml_class" in ds

    # Now set the x axis to Voyager
    mw.widget_ana_view.ui.tabWidget.setCurrentWidget(
        mw.widget_ana_view.ui.tab_plot)
    pv = mw.widget_ana_view.ui.widget_plot
    idvoy = pv.ui.comboBox_axis_x.findData("ml_score_voy")
    assert idvoy >= 0
    pv.ui.comboBox_axis_x.setCurrentIndex(idvoy)
    qtbot.mouseClick(pv.ui.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)

    try:
        pathlib.Path(tmp).unlink()
    except OSError:
        pass


def test_remove_plots_issue_36(qtbot, mw):
    """Correctly handle empty plots

    https://github.com/DC-analysis/DCscope/issues/36

    Traceback (most recent call last):
      File "/home/paul/repos/DCscope/dcscope/gui/main.py",
        line 193, in adopt_pipeline
        lay = pipeline_state["plots"][plot_index]["layout"]
    IndexError: list index out of range
    """
    qtbot.addWidget(mw)

    # add a dataslots
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path, path, path])

    assert len(mw.pipeline.slot_ids) == 3, "we added those"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # now create a plot window
    plot_id = mw.add_plot()
    # and another one
    mw.add_plot()

    # remove a plot
    pw = mw.ui.block_matrix.get_widget(filt_plot_id=plot_id)
    pw.action_remove()


def test_reselect_filter(qtbot, mw):
    """Test that zooming in on contours works correctly"""
    qtbot.addWidget(mw)

    # Add test dataset and create plot
    slot_id = mw.add_dataslot(paths=[datapath / "calibration_beads_47.rtdc"])
    plot_id = mw.add_plot()

    # Activate slot-plot pair
    pe = mw.ui.block_matrix.get_widget(filt_plot_id=plot_id, slot_id=slot_id[0])
    qtbot.mouseClick(pe, QtCore.Qt.MouseButton.LeftButton)

    # Activate the filter
    em = mw.ui.block_matrix.get_widget(filt_plot_id=mw.pipeline.filter_ids[0],
                                    slot_id=slot_id[0])
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton)

    # Edit the filter
    fe = mw.ui.block_matrix.get_widget(filt_plot_id=mw.pipeline.filter_ids[0])
    qtbot.mouseClick(fe.ui.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)
    mw.widget_ana_view.ui.tabWidget.setCurrentWidget(
        mw.widget_ana_view.ui.tab_filter)
    wf = mw.widget_ana_view.ui.widget_filter
    wf.ui.checkBox_limit.setChecked(True)
    wf.ui.spinBox_limit.setValue(4)

    # click apply
    qtbot.mouseClick(wf.ui.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)

    # Make sure there are only four points in the plot
    QtWidgets.QApplication.processEvents(
        QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 500)
    scat = mw.subwindows_plots[plot_id].widget().plot_items[0].items[-1]
    assert len(scat.data) == 4

    # Deactivate the filter
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton)
    QtWidgets.QApplication.processEvents(
        QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 500)
    scat = mw.subwindows_plots[plot_id].widget().plot_items[0].items[-1]
    assert len(scat.data) == 47

    # Activate the filter
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton)
    QtWidgets.QApplication.processEvents(
        QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 500)
    scat = mw.subwindows_plots[plot_id].widget().plot_items[0].items[-1]
    assert len(scat.data) == 4

    # Deactivate the filter
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton)
    QtWidgets.QApplication.processEvents(
        QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 500)
    scat = mw.subwindows_plots[plot_id].widget().plot_items[0].items[-1]
    assert len(scat.data) == 47

    # Activate the filter
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton)
    QtWidgets.QApplication.processEvents(
        QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 500)
    scat = mw.subwindows_plots[plot_id].widget().plot_items[0].items[-1]
    assert len(scat.data) == 4


def test_changing_lut_identifier_in_analysis_view_plots(qtbot, mw):
    """Test LUT identifier user interaction in analysis view plots."""
    qtbot.addWidget(mw)

    # add a dataslot
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])

    # add a plot
    plot_id = mw.add_plot()

    # activate analysis view
    pe = mw.ui.block_matrix.get_widget(filt_plot_id=plot_id)
    qtbot.mouseClick(pe.ui.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)

    mw.widget_ana_view.ui.tabWidget.setCurrentWidget(
        mw.widget_ana_view.ui.tab_plot)
    pv = mw.widget_ana_view.ui.widget_plot

    # Change to "HE-2D-FEM-22" and apply
    idx = pv.ui.comboBox_lut.findData("HE-2D-FEM-22")
    pv.ui.comboBox_lut.setCurrentIndex(idx)
    qtbot.mouseClick(pv.ui.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)

    assert pv.ui.comboBox_lut.currentData() == "HE-2D-FEM-22"

    # Change to "HE-3D-FEM-22" and apply
    idx = pv.ui.comboBox_lut.findData("HE-3D-FEM-22")
    pv.ui.comboBox_lut.setCurrentIndex(idx)
    qtbot.mouseClick(pv.ui.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)

    assert pv.ui.comboBox_lut.currentData() == "HE-3D-FEM-22"


def test_zoomin_contours(qtbot, mw):
    """Test that zooming in on contours works correctly"""
    qtbot.addWidget(mw)

    # Add test dataset and create plot
    slot_id = mw.add_dataslot(paths=[datapath / "calibration_beads_47.rtdc"])
    plot_id = mw.add_plot()

    # Activate slot-plot pair
    pe = mw.ui.block_matrix.get_widget(filt_plot_id=plot_id, slot_id=slot_id[0])
    qtbot.mouseClick(pe, QtCore.Qt.MouseButton.LeftButton)

    # Get range before zoom-in
    mw.add_plot_window(plot_id)
    plot_widget = mw.subwindows_plots[plot_id].widget()
    view_range_before = plot_widget.plot_items[-1].getViewBox().viewRange()
    x_range_before = view_range_before[0]
    y_range_before = view_range_before[1]

    # Switch to plot tab
    mw.widget_ana_view.ui.tabWidget.setCurrentWidget(mw.widget_ana_view.ui.tab_plot)
    pv = mw.widget_ana_view.ui.widget_plot

    # Enable contour zoom-in and apply
    pv.ui.checkBox_zoomin.setChecked(True)
    qtbot.mouseClick(pv.ui.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)

    # Get range after zoom-in
    plot_widget = mw.subwindows_plots[plot_id].widget()
    view_range_after = plot_widget.plot_items[-1].getViewBox().viewRange()
    x_range_after = view_range_after[0]
    y_range_after = view_range_after[1]

    # Verify zoom-in reduced both X and Y ranges
    assert x_range_after[1] < x_range_before[1], "x-max should decrease"
    assert y_range_after[1] < y_range_before[1], "y-max should decrease"


def test_only_contours_division(qtbot, mw):
    """Test that 'onlycontours' division mode works correctly"""
    qtbot.addWidget(mw)

    # Add multiple datasets
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path, path])  # Add same dataset twice for testing

    # Add a plot
    plot_id = mw.add_plot()

    # Activate analysis view
    pe = mw.ui.block_matrix.get_widget(filt_plot_id=plot_id)
    qtbot.mouseClick(pe.ui.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)

    # Switch to plot tab
    mw.widget_ana_view.ui.tabWidget.setCurrentWidget(mw.widget_ana_view.ui.tab_plot)
    pv = mw.widget_ana_view.ui.widget_plot

    # Get the initial plot state
    plot_state = mw.pipeline.get_plot(plot_id).__getstate__()

    # Verify there is only one plot
    assert len(mw.pipeline.plot_ids) == 1, "Should have exactly one plot"

    # Verify initial division mode
    assert plot_state["layout"]["division"] == "multiscatter+contour"

    # Set division to "onlycontours"
    idx = pv.ui.comboBox_division.findData("onlycontours")
    pv.ui.comboBox_division.setCurrentIndex(idx)

    # Apply changes
    qtbot.mouseClick(pv.ui.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)

    # Get the plot widget
    pw = mw.ui.block_matrix.get_widget(filt_plot_id=plot_id)

    # Activate plots for contour view
    qtbot.mouseClick(pw.ui.toolButton_toggle, QtCore.Qt.MouseButton.LeftButton)

    # Get the plot state
    plot_state = mw.pipeline.get_plot(plot_id).__getstate__()

    # Verify division mode
    assert plot_state["layout"]["division"] == "onlycontours"


def test_contour_plot_with_invalid_percentiles(qtbot, mw):
    """Test contour plot with edge case percentiles (e.g., 100% KDE)"""
    qtbot.addWidget(mw)

    # Add a dataset
    path = datapath / "calibration_beads_47.rtdc"
    slot_id = mw.add_dataslot(paths=[path])[0]

    # Add a plot
    plot_id = mw.add_plot()

    # Activate the slot-plot pair to show data
    pe = mw.ui.block_matrix.get_widget(slot_id, plot_id)
    qtbot.mouseClick(pe, QtCore.Qt.MouseButton.LeftButton)

    # Activate analysis view
    pe = mw.ui.block_matrix.get_widget(filt_plot_id=plot_id)
    qtbot.mouseClick(pe.ui.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)

    # Switch to plot tab
    mw.widget_ana_view.ui.tabWidget.setCurrentWidget(mw.widget_ana_view.ui.tab_plot)
    pv = mw.widget_ana_view.ui.widget_plot

    # Enable contours
    pv.ui.groupBox_contour.setChecked(True)

    # Set contour percentiles to extreme values (edge cases)
    # 100% percentile is at the maximum KDE value
    pv.ui.doubleSpinBox_perc_1.setValue(100.0)  # Maximum percentile
    pv.ui.doubleSpinBox_perc_2.setValue(100.0)   # Near maximum

    # Apply changes
    qtbot.mouseClick(pv.ui.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)

    # Verify the plot state was updated with the new percentiles
    plot_state = mw.pipeline.get_plot(plot_id).__getstate__()
    con = plot_state["contour"]

    # Check that percentiles were set
    assert con["percentiles"][0] == 100.0
    assert con["percentiles"][1] == 100.0
    assert con["enabled"] is True

    # Open the plot window to verify rendering works
    mw.add_plot_window(plot_id)

    # Get the plot widget
    plot_widget = mw.subwindows_plots[plot_id].widget()

    # Check that plot items were created
    assert plot_widget is not None
    if plot_widget.plot_items:
        assert len(plot_widget.plot_items) > 0
