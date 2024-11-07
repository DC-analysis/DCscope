"""Plotting GUI tests"""
import pathlib
import tempfile

import dclab
import h5py
import numpy as np
from PyQt6 import QtCore
import pytest
from shapeout2.gui.main import ShapeOut2
from shapeout2 import pipeline, session


datapath = pathlib.Path(__file__).parent / "data"


@pytest.fixture(autouse=True)
def run_around_tests():
    # Code that will run before your test, for example:
    session.clear_session()
    # A test function will be run at this point
    yield
    # Code that will run after your test, for example:
    session.clear_session()


def test_empty_plot_with_one_plot_per_dataset_issue_41(qtbot):
    """
    Setting "one plot per dataset" for an empty plot resulted in
    zero-division error when determining col/row numbers
    """
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # add a dataslot
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])

    # add a plot
    plot_id = mw.add_plot()

    # activate analysis view
    pe = mw.block_matrix.get_widget(filt_plot_id=plot_id)
    qtbot.mouseClick(pe.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)

    pv = mw.widget_ana_view.widget_plot

    # Change to "each" and apply
    idx = pv.comboBox_division.findData("each")
    pv.comboBox_division.setCurrentIndex(idx)
    # Lead to zero-division error in "get_plot_col_row_count"
    qtbot.mouseClick(pv.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)


def test_feature_bright_avg_not_present_issue_62(qtbot):
    """Plot a dataset that does not contain the "bright_avg" feature

    ...or any means of computing it (i.e. via "image")
    """
    # create fake dataset without bright_avg
    tmp = tempfile.mktemp(".rtdc", prefix="example_hue_")
    with dclab.new_dataset(datapath / "calibration_beads_47.rtdc") as ds:
        ds.export.hdf5(tmp, features=["area_um", "pos_x", "pos_y", "deform"])

    mw = ShapeOut2()
    qtbot.addWidget(mw)
    # add dataset
    slot_id = mw.add_dataslot([tmp])[0]
    # add plot
    plot_id = mw.add_plot()
    # and activate it
    pw = mw.block_matrix.get_widget(filt_plot_id=plot_id, slot_id=slot_id)
    # this raised "ValueError: 'bright_avg' is not in list" (issue #62)
    qtbot.mouseClick(pw, QtCore.Qt.MouseButton.LeftButton)


def test_handle_axis_selection_empty_plot(qtbot):
    """User did not add a dataset to a plot and starts changing plot params"""
    mw = ShapeOut2()
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
    pe = mw.block_matrix.get_widget(filt_plot_id=plot_id)
    qtbot.mouseClick(pe.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)

    pv = mw.widget_ana_view.widget_plot

    # This lead to:
    #    Traceback (most recent call last):
    #  File "/ShapeOut2/shapeout2/gui/analysis/ana_plot.py",
    #     line 406, in on_axis_changed
    #    self._set_contour_spacing_auto(axis_y=gen["axis y"])
    #  File "/ShapeOut2/shapeout2/gui/analysis/ana_plot.py",
    #     line 361, in _set_contour_spacing_auto
    #    spacings_xy.append(np.min(spacings))
    #  File "/numpy/core/fromnumeric.py", line 2618, in amin
    #    initial=initial)
    #  File "/numpy/core/fromnumeric.py", line 86, in _wrapreduction
    #    return ufunc.reduce(obj, axis, dtype, out, **passkwargs)
    # ValueError: zero-size array to reduction operation minimum which
    # has no identity
    pv.comboBox_axis_y.setCurrentIndex(pv.comboBox_axis_y.findData("emodulus"))


def test_handle_empty_plots_issue_27(qtbot):
    """Correctly handle empty plots

    https://github.com/ZELLMECHANIK-DRESDEN/ShapeOut2/issues/27
    """
    mw = ShapeOut2()
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
    em = mw.block_matrix.get_widget(slot_id, filt_id)
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton)  # activate
    # did that work?
    assert mw.pipeline.is_element_active(slot_id, filt_id)

    # filter away all events
    fe = mw.block_matrix.get_widget(filt_plot_id=filt_id)
    qtbot.mouseClick(fe.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)
    fv = mw.widget_ana_view.widget_filter
    qtbot.mouseClick(fv.toolButton_moreless, QtCore.Qt.MouseButton.LeftButton)
    rc = fv._box_range_controls["area_um"]
    qtbot.mouseClick(rc.checkBox, QtCore.Qt.MouseButton.LeftButton)
    # did that work?
    assert rc.checkBox.isChecked()
    qtbot.mouseClick(fv.toolButton_moreless, QtCore.Qt.MouseButton.LeftButton)
    # set range
    rc.doubleSpinBox_min.setValue(0)
    rc.doubleSpinBox_max.setValue(1)
    qtbot.mouseClick(fv.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)
    # did that work?
    ds = mw.pipeline.get_dataset(slot_index=0, filt_index=0,
                                 apply_filter=True)
    assert np.sum(ds.filter.all) == 0

    # now create a plot window
    plot_id = mw.add_plot()
    pe = mw.block_matrix.get_widget(slot_id, plot_id)
    with pytest.warns(pipeline.core.EmptyDatasetWarning):
        # this now only throws a warning
        # activate (raises #27)
        qtbot.mouseClick(pe, QtCore.Qt.MouseButton.LeftButton)


@pytest.mark.filterwarnings(
    'ignore::dclab.features.emodulus.YoungsModulusLookupTableExceededWarning')
def test_handle_nan_valued_feature_color(qtbot):
    """User wants to color scatter data points with feature containing nans"""
    spath = datapath / "version_2_1_2_plot_color_emodulus.so2"

    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # lead to:
    # OverflowError: argument 4 overflowed: value must be in the range
    # -2147483648 to 2147483647
    mw.on_action_open(spath)


def test_hue_feature_not_computed_if_not_selected(qtbot):
    # generate .rtdc file without bright_avg feature
    tmp = tempfile.mktemp(".rtdc", prefix="example_hue_")
    with dclab.new_dataset(datapath / "calibration_beads_47.rtdc") as ds:
        ds.export.hdf5(tmp, features=["area_um", "pos_x", "pos_y", "image",
                                      "mask", "deform"])
    mw = ShapeOut2()
    qtbot.addWidget(mw)
    # add dataset
    slot_id = mw.add_dataslot([tmp])[0]
    # add plot
    plot_id = mw.add_plot()
    # and activate it
    pw = mw.block_matrix.get_widget(filt_plot_id=plot_id, slot_id=slot_id)
    qtbot.mouseClick(pw, QtCore.Qt.MouseButton.LeftButton)
    # get the dataset
    ds = mw.pipeline.get_dataset(slot_index=0)
    # check whether the item has been plotted
    datasets, _ = mw.pipeline.get_plot_datasets(plot_id)
    assert datasets[0] is ds
    # now check whether "bright_avg" has been computed
    assert "bright_avg" in ds.features
    assert "bright_avg" not in ds.features_loaded


def test_plot_ml_score(qtbot):
    tmp = tempfile.mktemp(".rtdc", prefix="example_ml_score_")
    with dclab.new_dataset(datapath / "calibration_beads_47.rtdc") as ds:
        ds.export.hdf5(tmp, features=["area_um", "pos_x", "pos_y", "image",
                                      "mask", "deform"])
        lends = len(ds)
    # add ml_score features
    with h5py.File(tmp, "a") as h5:
        h5["/events/ml_score_ds9"] = np.linspace(0, 1, lends)
        h5["/events/ml_score_voy"] = np.linspace(1, 0, lends)
    mw = ShapeOut2()
    qtbot.addWidget(mw)
    # add dataset
    slot_id = mw.add_dataslot([tmp])[0]
    # add plot
    plot_id = mw.add_plot()
    # and activate it
    pw = mw.block_matrix.get_widget(filt_plot_id=plot_id, slot_id=slot_id)
    qtbot.mouseClick(pw, QtCore.Qt.MouseButton.LeftButton)
    # get the dataset
    ds = mw.pipeline.get_dataset(slot_index=0)
    # sanity check
    assert "ml_class" in ds

    # Now set the x axis to Voyager
    pv = mw.widget_ana_view.widget_plot
    idvoy = pv.comboBox_axis_x.findData("ml_score_voy")
    assert idvoy >= 0
    pv.comboBox_axis_x.setCurrentIndex(idvoy)
    qtbot.mouseClick(pv.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)

    try:
        pathlib.Path(tmp).unlink()
    except OSError:
        pass


def test_remove_plots_issue_36(qtbot):
    """Correctly handle empty plots

    https://github.com/ZELLMECHANIK-DRESDEN/ShapeOut2/issues/36

    Traceback (most recent call last):
      File "/home/paul/repos/ShapeOut2/shapeout2/gui/main.py",
        line 193, in adopt_pipeline
        lay = pipeline_state["plots"][plot_index]["layout"]
    IndexError: list index out of range
    """
    mw = ShapeOut2()
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
    pw = mw.block_matrix.get_widget(filt_plot_id=plot_id)
    pw.action_remove()


def test_changing_lut_identifier_in_analysis_view_plots(qtbot):
    """Test LUT identifier user interaction in analysis view plots."""
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # add a dataslot
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])

    # add a plot
    plot_id = mw.add_plot()

    # activate analysis view
    pe = mw.block_matrix.get_widget(filt_plot_id=plot_id)
    qtbot.mouseClick(pe.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)

    pv = mw.widget_ana_view.widget_plot

    # Change to "HE-2D-FEM-22" and apply
    idx = pv.comboBox_lut.findData("HE-2D-FEM-22")
    pv.comboBox_lut.setCurrentIndex(idx)
    qtbot.mouseClick(pv.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)

    assert pv.comboBox_lut.currentData() == "HE-2D-FEM-22"

    # Change to "HE-3D-FEM-22" and apply
    idx = pv.comboBox_lut.findData("HE-3D-FEM-22")
    pv.comboBox_lut.setCurrentIndex(idx)
    qtbot.mouseClick(pv.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)

    assert pv.comboBox_lut.currentData() == "HE-3D-FEM-22"
