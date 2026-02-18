"""Test of filter functionalities"""
import copy
import pathlib
import tempfile

import dclab
import numpy as np
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QEventLoop

from dcscope.gui.main import DCscope
from dcscope import session
import pytest


data_path = pathlib.Path(__file__).parent / "data"


def make_fake_dataset():
    """Return path of a temporary .rtdc file"""
    path = data_path / "calibration_beads_47.rtdc"
    with dclab.new_dataset(path) as ds:
        config = copy.deepcopy(ds.config)

    tmp = tempfile.mktemp(".rtdc", prefix="example_filter_inf_")
    ddict = {"deform": np.linspace(0, .01, 100),
             "area_um": np.linspace(20, 200, 100),
             "area_ratio": np.linspace(1, 1.1, 100)
             }
    ddict["area_ratio"][0] = np.inf
    ddict["area_ratio"][1] = np.nan
    ds2 = dclab.new_dataset(ddict)
    ds2.config.update(config)
    ds2.config["experiment"]["event count"] = 100
    ds2.export.hdf5(tmp, features=["area_um", "deform", "area_ratio"])
    return tmp


@pytest.fixture(autouse=True)
def run_around_tests():
    # Code that will run before your test, for example:
    session.clear_session()
    # A test function will be run at this point
    yield
    # Code that will run after your test, for example:
    session.clear_session()


def test_box_filter_selection_no_preselection_issue_67(qtbot):
    """
    The user creates a filter and selects a few features for box
    filtering. Then the user creates a new filter and tries to add
    new box filters. There should not be any preselected filters.
    """
    path = make_fake_dataset()

    mw = DCscope()
    qtbot.addWidget(mw)

    # add the file
    mw.add_dataslot(paths=[path])

    # edit the initial filter in the Analysis View
    fe = mw.block_matrix.get_widget(filt_plot_id=mw.pipeline.filter_ids[0])
    qtbot.mouseClick(fe.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)

    # box filtering
    mw.widget_ana_view.tabWidget.setCurrentWidget(
        mw.widget_ana_view.tab_filter)
    wf = mw.widget_ana_view.widget_filter
    # enable selection
    qtbot.mouseClick(wf.toolButton_moreless, QtCore.Qt.MouseButton.LeftButton)
    # find the porosity item and click the checkbox
    rc = wf._box_range_controls["area_ratio"]
    qtbot.mouseClick(rc.checkBox, QtCore.Qt.MouseButton.LeftButton)
    # disable selection
    qtbot.mouseClick(wf.toolButton_moreless, QtCore.Qt.MouseButton.LeftButton)

    # now add second filter
    mw.add_filter()

    # edit the second filter in the Analysis View
    fe = mw.block_matrix.get_widget(filt_plot_id=mw.pipeline.filter_ids[1])
    qtbot.mouseClick(fe.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)

    # make sure that "area_ratio" is not preselected
    wf = mw.widget_ana_view.widget_filter
    mw.widget_ana_view.tabWidget.setCurrentWidget(
        mw.widget_ana_view.tab_filter)

    # enable selection
    qtbot.mouseClick(wf.toolButton_moreless, QtCore.Qt.MouseButton.LeftButton)
    # find the porosity item and click the checkbox
    rc = wf._box_range_controls["area_ratio"]
    assert not rc.checkBox.isChecked()
    # and a sanity check
    rc2 = wf._box_range_controls["deform"]
    assert not rc2.checkBox.isChecked()

    # cleanup: disable selection
    qtbot.mouseClick(wf.toolButton_moreless, QtCore.Qt.MouseButton.LeftButton)


def test_filter_min_max_delete(qtbot):
    """Create a box filter, apply it, and delete it again"""
    path = make_fake_dataset()

    mw = DCscope()
    qtbot.addWidget(mw)

    # add the file
    mw.add_dataslot(paths=[path, path])

    assert len(mw.pipeline.slot_ids) == 2, "we added that"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"
    # sanity check
    ds10 = dclab.new_dataset(mw.pipeline.get_dataset(0))
    ds20 = dclab.new_dataset(mw.pipeline.get_dataset(0))
    assert np.max(ds10["area_um"]) > 20
    assert np.max(ds20["area_um"]) > 20

    # open the filter edit in the Analysis View
    fe = mw.block_matrix.get_widget(filt_plot_id=mw.pipeline.filter_ids[0])
    qtbot.mouseClick(fe.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)

    # box filtering
    wf = mw.widget_ana_view.widget_filter
    mw.widget_ana_view.tabWidget.setCurrentWidget(
        mw.widget_ana_view.tab_filter)

    # enable selection
    qtbot.mouseClick(wf.toolButton_moreless, QtCore.Qt.MouseButton.LeftButton)
    # find the porosity item and click the checkbox
    rc = wf._box_range_controls["area_um"]
    qtbot.mouseClick(rc.checkBox, QtCore.Qt.MouseButton.LeftButton)
    # disable selection
    qtbot.mouseClick(wf.toolButton_moreless, QtCore.Qt.MouseButton.LeftButton)

    # set the range control for area from 20 to 30 µm
    rc.doubleSpinBox_min.setValue(20)
    rc.doubleSpinBox_max.setValue(30)

    # click apply
    qtbot.mouseClick(wf.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)

    # make sure this worked
    assert rc.read_pipeline_state()["end"] == 30
    box_filters = mw.pipeline.filters[0].__getstate__()["box filters"]
    assert box_filters["area_um"]["end"] == 30
    assert box_filters["area_um"]["active"] is True

    # activate the filter for both datasets
    me1 = mw.block_matrix.get_widget(filt_plot_id=mw.pipeline.filter_ids[0],
                                     slot_id=mw.pipeline.slot_ids[0]
                                     )
    qtbot.mouseClick(me1, QtCore.Qt.MouseButton.LeftButton)
    me2 = mw.block_matrix.get_widget(filt_plot_id=mw.pipeline.filter_ids[0],
                                     slot_id=mw.pipeline.slot_ids[1]
                                     )
    qtbot.mouseClick(me2, QtCore.Qt.MouseButton.LeftButton)

    QtWidgets.QApplication.processEvents(
        QEventLoop.ProcessEventsFlag.AllEvents, 500)

    assert len(mw.pipeline.get_filters_for_slot(mw.pipeline.slot_ids[0])) == 1
    assert len(mw.pipeline.get_filters_for_slot(mw.pipeline.slot_ids[1])) == 1

    # get the datasets from the pipeline and check that they are filtered
    ds1a = dclab.new_dataset(mw.pipeline.get_dataset(0))
    ds2a = dclab.new_dataset(mw.pipeline.get_dataset(1))

    # This is expected
    assert np.max(ds1a["area_um"]) < 30
    assert np.max(ds2a["area_um"]) < 30

    # Now, remove the box filter!
    qtbot.mouseClick(wf.toolButton_moreless, QtCore.Qt.MouseButton.LeftButton)
    # find the porosity item and click the checkbox
    rc = wf._box_range_controls["area_um"]
    qtbot.mouseClick(rc.checkBox, QtCore.Qt.MouseButton.LeftButton)
    # disable selection
    qtbot.mouseClick(wf.toolButton_moreless, QtCore.Qt.MouseButton.LeftButton)

    # click apply
    qtbot.mouseClick(wf.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)
    QtWidgets.QApplication.processEvents(
        QEventLoop.ProcessEventsFlag.AllEvents, 500)

    # make sure this worked
    box_filters = mw.pipeline.filters[0].__getstate__()["box filters"]
    assert "area_um" not in box_filters

    # get the datasets from the pipeline and check that they are filtered
    ds1b = dclab.new_dataset(mw.pipeline.get_dataset(0))
    ds2b = dclab.new_dataset(mw.pipeline.get_dataset(1))

    # This was the bug. The filters were not removed correctly.
    assert np.max(ds1b["area_um"]) > 30
    assert np.max(ds2b["area_um"]) > 30


def test_filter_min_max_inf(qtbot):
    path = make_fake_dataset()

    mw = DCscope()
    qtbot.addWidget(mw)

    # add the file
    mw.add_dataslot(paths=[path])

    assert len(mw.pipeline.slot_ids) == 1, "we added that"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # open the filter edit in the Analysis View
    fe = mw.block_matrix.get_widget(filt_plot_id=mw.pipeline.filter_ids[0])
    qtbot.mouseClick(fe.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)

    # box filtering
    wf = mw.widget_ana_view.widget_filter
    mw.widget_ana_view.tabWidget.setCurrentWidget(
        mw.widget_ana_view.tab_filter)

    # enable selection
    qtbot.mouseClick(wf.toolButton_moreless, QtCore.Qt.MouseButton.LeftButton)
    # find the porosity item and click the checkbox
    rc = wf._box_range_controls["area_ratio"]
    qtbot.mouseClick(rc.checkBox, QtCore.Qt.MouseButton.LeftButton)
    # disable selection
    qtbot.mouseClick(wf.toolButton_moreless, QtCore.Qt.MouseButton.LeftButton)

    # check that the range control does not have all-zero values
    rcstate = rc.read_pipeline_state()
    assert rcstate["start"] != 0
    assert rcstate["end"] != 0
    # only approximate (b/c they were converted on the range scale)
    ds = dclab.new_dataset(path)
    assert np.allclose(rcstate["start"], ds["area_ratio"][2], rtol=1e-4)
    assert np.allclose(rcstate["end"], 1.1, rtol=1e-4)


def test_polygon_filter_basic(qtbot):
    path = data_path / "calibration_beads_47.rtdc"

    with dclab.new_dataset(path) as ds:
        pf1 = dclab.PolygonFilter(
            axes=("deform", "area_um"),
            points=[[np.min(ds["deform"]), np.min(ds["area_um"])],
                    [np.min(ds["deform"]), np.mean(ds["area_um"])],
                    [np.mean(ds["deform"]), np.mean(ds["area_um"])],
                    ],
            name="Triangle of Death",
        )

    mw = DCscope()
    qtbot.addWidget(mw)

    # add the file
    mw.add_dataslot(paths=[path])

    # enable the filter
    slot_id = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em = mw.block_matrix.get_widget(slot_id, filt_id)
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton)
    # did that work?
    assert mw.pipeline.is_element_active(slot_id, filt_id)

    assert len(mw.pipeline.slot_ids) == 1, "we added that"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # open the filter edit in the Analysis View
    fe = mw.block_matrix.get_widget(filt_plot_id=mw.pipeline.filter_ids[0])
    qtbot.mouseClick(fe.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)

    # enable the polygon filter
    wf = mw.widget_ana_view.widget_filter
    mw.widget_ana_view.tabWidget.setCurrentWidget(
        mw.widget_ana_view.tab_filter)

    filter_ids = list(wf._polygon_checkboxes.keys())
    # sanity check
    assert filter_ids == [pf1.unique_id]

    wf._polygon_checkboxes[pf1.unique_id].setChecked(True)
    assert wf._polygon_checkboxes[pf1.unique_id].isChecked()

    # click apply
    qtbot.mouseClick(wf.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)

    # check the filter
    assert pf1.unique_id in mw.pipeline.filters[0].polylist

    # get the dataset
    assert len(mw.pipeline.slots) == 1
    assert len(mw.pipeline.filters) == 1
    ds_slot = mw.pipeline.slots[0].get_dataset()
    ds = mw.pipeline.get_dataset(0)
    assert ds_slot is not ds
    assert np.sum(ds.filter.all) == 5
    assert len(ds) == 5


def test_polygon_filter_delete(qtbot):
    path = data_path / "calibration_beads_47.rtdc"

    with dclab.new_dataset(path) as ds:
        pf1 = dclab.PolygonFilter(
            axes=("deform", "area_um"),
            points=[[np.min(ds["deform"]), np.min(ds["area_um"])],
                    [np.min(ds["deform"]), np.mean(ds["area_um"])],
                    [np.mean(ds["deform"]), np.mean(ds["area_um"])],
                    ],
            name="Triangle of Death",
        )

    mw = DCscope()
    qtbot.addWidget(mw)

    # add the file
    mw.add_dataslot(paths=[path])

    # enable the filter
    slot_id = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em = mw.block_matrix.get_widget(slot_id, filt_id)
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton)
    # did that work?
    assert mw.pipeline.is_element_active(slot_id, filt_id)

    assert len(mw.pipeline.slot_ids) == 1, "we added that"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # open the filter edit in the Analysis View
    fe = mw.block_matrix.get_widget(filt_plot_id=mw.pipeline.filter_ids[0])
    qtbot.mouseClick(fe.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)

    # enable the polygon filter
    wf = mw.widget_ana_view.widget_filter
    mw.widget_ana_view.tabWidget.setCurrentWidget(
        mw.widget_ana_view.tab_filter)

    filter_ids = list(wf._polygon_checkboxes.keys())
    # sanity check
    assert filter_ids == [pf1.unique_id]

    wf._polygon_checkboxes[pf1.unique_id].setChecked(True)
    assert wf._polygon_checkboxes[pf1.unique_id].isChecked()

    # click apply
    qtbot.mouseClick(wf.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)

    # check the filter
    assert pf1.unique_id in mw.pipeline.filters[0].polylist

    # now remove the filter
    em1 = mw.block_matrix.get_widget(slot_id, filt_id)
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)
    qv = mw.widget_quick_view
    qtbot.mouseClick(qv.toolButton_poly, QtCore.Qt.MouseButton.LeftButton)
    qv.comboBox_poly.setCurrentIndex(1)
    QtWidgets.QApplication.processEvents(
        QEventLoop.ProcessEventsFlag.AllEvents, 300)
    assert qv.pushButton_poly_save.isVisible()
    assert qv.pushButton_poly_cancel.isVisible()
    assert qv.pushButton_poly_delete.isVisible()
    qtbot.mouseClick(qv.pushButton_poly_delete,
                     QtCore.Qt.MouseButton.LeftButton)
    assert not qv.pushButton_poly_delete.isVisible()

    # did that work?
    assert len(mw.pipeline.filters[0].polylist) == 0

    # get the dataset
    assert len(mw.pipeline.slots) == 1
    assert len(mw.pipeline.filters) == 1

    ds = mw.pipeline.get_dataset(0)
    assert np.sum(ds.filter.all) == 47
    assert len(ds) == 47
