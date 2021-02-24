"""Test of Quick View set functionalities"""
import pathlib

from PyQt5 import QtCore

import dclab
import numpy as np
from shapeout2.gui.main import ShapeOut2
from shapeout2 import session
import pytest


datapath = pathlib.Path(__file__).parent / "data"


@pytest.fixture(autouse=True)
def run_around_tests():
    # Code that will run before your test, for example:
    session.clear_session()
    # A test function will be run at this point
    yield
    # Code that will run after your test, for example:
    session.clear_session()


def test_simple(qtbot):
    """Open the main window and close it again"""
    main_window = ShapeOut2()
    main_window.close()


def test_clear_session_issue_25(qtbot):
    """https://github.com/ZELLMECHANIK-DRESDEN/ShapeOut2/issues/25"""
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # add a dataslot
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])

    assert len(mw.pipeline.slot_ids) == 1, "we added that"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # activate a dataslot
    slot_id = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em = mw.block_matrix.get_widget(slot_id, filt_id)
    qtbot.mouseClick(em, QtCore.Qt.LeftButton, QtCore.Qt.ShiftModifier)
    # did that work?
    assert mw.toolButton_quick_view.isChecked()

    # now clear the session (this raised the errror in #25)
    mw.on_action_clear(assume_yes=True)


@pytest.mark.filterwarnings('ignore::RuntimeWarning')  # 0-div in kde-methods
@pytest.mark.filterwarnings('ignore::shapeout2.pipeline.core.'
                            + 'EmptyDatasetWarning')
def test_no_events_disable(qtbot):
    """When all events are removed, a message should be displayed"""
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # This session also contains a plot, so this is essentially
    # also a test for empty plots.
    spath = datapath / "version_2_1_6_no_events.so2"
    mw.on_action_open(spath)

    # Matrix widgets
    slot_id1 = mw.pipeline.slot_ids[0]
    slot_id2 = mw.pipeline.slot_ids[1]
    filt_id = mw.pipeline.filter_ids[0]
    em1 = mw.block_matrix.get_widget(slot_id1, filt_id)
    em2 = mw.block_matrix.get_widget(slot_id2, filt_id)

    # Now activate Quick View
    qtbot.mouseClick(em1, QtCore.Qt.LeftButton, QtCore.Qt.ShiftModifier)

    # Get Quick View instance
    qv = mw.widget_quick_view

    # This will display the "Hoppla!" message
    assert qv.label_noevents.isVisible()

    # Check the reverse
    qtbot.mouseClick(em2, QtCore.Qt.LeftButton, QtCore.Qt.ShiftModifier)
    assert not qv.label_noevents.isVisible()


def test_no_events_issue_37(qtbot):
    """https://github.com/ZELLMECHANIK-DRESDEN/ShapeOut2/issues/37

    "ValueError: zero-size array to reduction operation minimum
    which has no identity" when all events are filtered out.
    """
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # add a dataslot
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path, path])

    assert len(mw.pipeline.slot_ids) == 2, "we added those"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # activate a dataslot
    slot_id = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em = mw.block_matrix.get_widget(slot_id, filt_id)
    qtbot.mouseClick(em, QtCore.Qt.LeftButton)  # activate
    # did that work?
    assert mw.pipeline.is_element_active(slot_id, filt_id)

    # filter away all events
    fe = mw.block_matrix.get_widget(filt_plot_id=filt_id)
    qtbot.mouseClick(fe.toolButton_modify, QtCore.Qt.LeftButton)
    fv = mw.widget_ana_view.widget_filter
    qtbot.mouseClick(fv.toolButton_moreless, QtCore.Qt.LeftButton)
    rc = fv._box_range_controls["area_um"]
    qtbot.mouseClick(rc.checkBox, QtCore.Qt.LeftButton)
    # did that work?
    assert rc.checkBox.isChecked()
    qtbot.mouseClick(fv.toolButton_moreless, QtCore.Qt.LeftButton)
    # set range
    rc.doubleSpinBox_min.setValue(0)
    rc.doubleSpinBox_max.setValue(1)
    qtbot.mouseClick(fv.pushButton_apply, QtCore.Qt.LeftButton)
    # did that work?
    ds = mw.pipeline.get_dataset(slot_index=0, filt_index=0,
                                 apply_filter=True)
    assert np.sum(ds.filter.all) == 0

    # open QuickView
    slot_id = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em = mw.block_matrix.get_widget(slot_id, filt_id)

    # this raised the error
    qtbot.mouseClick(em, QtCore.Qt.LeftButton, QtCore.Qt.ShiftModifier)
    mw.close()


def test_remove_dataset_h5py_error(qtbot):
    """Removing an activated dataset and activating Quick View fails

    Unhandled exception in Shape-Out version 2.0.1.post2:
    Traceback (most recent call last):
      File "/home/paul/repos/ShapeOut2/shapeout2/gui/main.py", line 235,
        in adopt_pipeline
        self.widget_quick_view.update_feature_choices()
      File "/home/paul/repos/ShapeOut2/shapeout2/gui/quick_view/qv_main.py",
        line 635, in update_feature_choices
        ds_feats = [f for f in self.rtdc_ds.features if f in feats_scalar]
    [...]
      File "/home/paul/repos/dclab/dclab/rtdc_dataset/fmt_hdf5.py", line 101,
        in _is_defective_feature
        if attr in self._h5.attrs:
    [...]
      File "h5py/_objects.pyx", line 55, in h5py._objects.with_phil.wrapper
      File "h5py/h5o.pyx", line 190, in h5py.h5o.open
    ValueError: Not a location (invalid object ID)
    """
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # add a dataslot
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path, path])

    assert len(mw.pipeline.slot_ids) == 2, "we added those"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # activate a dataslot
    slot_id = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em = mw.block_matrix.get_widget(slot_id, filt_id)
    qtbot.mouseClick(em, QtCore.Qt.LeftButton)  # activate
    qtbot.mouseClick(em, QtCore.Qt.LeftButton, QtCore.Qt.ShiftModifier)
    # did that work?
    assert mw.pipeline.is_element_active(slot_id, filt_id)

    # close Quick View
    qtbot.mouseClick(mw.toolButton_quick_view, QtCore.Qt.LeftButton)

    # now remove the dataset
    pw = mw.block_matrix.get_widget(slot_id=slot_id)
    pw.action_remove()

    # open Quick View
    qtbot.mouseClick(mw.toolButton_quick_view, QtCore.Qt.LeftButton)
    mw.close()


def test_update_polygon_filter_issue_26(qtbot):
    """https://github.com/ZELLMECHANIK-DRESDEN/ShapeOut2/issues/26

    The recomputation of the filter ray was not triggered for some
    reason.
    """
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # add a dataslot
    path = datapath / "calibration_beads_47.rtdc"
    filt_id = mw.add_filter()
    slot_ids = mw.add_dataslot(paths=[path])

    assert len(mw.pipeline.slot_ids) == 1, "we added that"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # activate a dataslot
    slot_id = slot_ids[0]
    em = mw.block_matrix.get_widget(slot_id, filt_id)
    qtbot.mouseClick(em, QtCore.Qt.LeftButton, QtCore.Qt.ShiftModifier)

    em = mw.block_matrix.get_widget(slot_id, filt_id)
    qtbot.mouseClick(em, QtCore.Qt.LeftButton)

    # did that work?
    assert mw.toolButton_quick_view.isChecked()

    # Add a polygon filter
    assert len(dclab.PolygonFilter.instances) == 0
    qv = mw.widget_quick_view
    qtbot.mouseClick(qv.toolButton_poly, QtCore.Qt.LeftButton)
    qtbot.mouseClick(qv.pushButton_poly_create, QtCore.Qt.LeftButton)
    # three positions (not sure how to do this with mouse clicks)
    points = [[22, 0.01],
              [30, 0.01],
              [30, 0.014],
              ]
    qv.widget_scatter.set_poly_points(points)
    qtbot.mouseClick(qv.pushButton_poly_save, QtCore.Qt.LeftButton)
    # did that work?
    assert len(dclab.PolygonFilter.instances) == 1
    pf = dclab.PolygonFilter.instances[0]
    assert np.allclose(pf.points, points)

    # Add the polygon filter to the first filter
    fe = mw.block_matrix.get_widget(filt_plot_id=filt_id)
    qtbot.mouseClick(fe.toolButton_modify, QtCore.Qt.LeftButton)
    fv = mw.widget_ana_view.widget_filter
    cb = fv._polygon_checkboxes[pf.unique_id]
    qtbot.mouseClick(cb, QtCore.Qt.LeftButton)
    assert cb.isChecked()
    qtbot.mouseClick(fv.pushButton_apply, QtCore.Qt.LeftButton)
    # did that work?
    ds = mw.pipeline.get_dataset(slot_index=0, filt_index=0,
                                 apply_filter=True)
    assert np.sum(ds.filter.all) == 15

    # Modify the polygon filter
    qv.comboBox_poly.setCurrentIndex(1)
    points2 = [[22, 0.01],
               [30, 0.01],
               [30, 0.012],
               ]
    qv.widget_scatter.set_poly_points(points2)
    qtbot.mouseClick(qv.pushButton_poly_save, QtCore.Qt.LeftButton)
    assert len(dclab.PolygonFilter.instances) == 1
    pf2 = dclab.PolygonFilter.instances[0]
    assert np.allclose(pf2.points, points2)
    assert pf is pf2
    # now the filter should be updated (this worked already)
    ds2 = mw.pipeline.get_dataset(slot_index=0, filt_index=0,
                                  apply_filter=True)
    assert np.sum(ds2.filter.all) == 8
    # but the plots were not updated in #26
    assert len(qv.widget_scatter.scatter.getData()[0]) == 8


def test_subtract_background(qtbot):
    """https://github.com/ZELLMECHANIK-DRESDEN/ShapeOut2/issues/54

    Adding the "Subtract Background"-CheckBox
    """

    # Create main window
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # Data with feature "image_bg"
    path1 = datapath / "artificial_with_image_bg.rtdc"

    # Data without feature "image_bg"
    path2 = datapath / "calibration_beads_47.rtdc"

    mw.add_dataslot(paths=[path1, path2])

    assert len(mw.pipeline.slot_ids) == 2, "we added those"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # Test if CheckBox is visible for dataset with feature "image_bg"
    # and if it is checked by default

    # Activate dataslots
    slot_id1 = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em1 = mw.block_matrix.get_widget(slot_id1, filt_id)

    # Activate
    qtbot.mouseClick(em1, QtCore.Qt.LeftButton)
    # Open QuickView-window
    qtbot.mouseClick(em1, QtCore.Qt.LeftButton, QtCore.Qt.ShiftModifier)

    # Check if QuickView-window is open
    assert mw.toolButton_quick_view.isChecked(), "Quickview not Open"

    # Get QuickView instance
    qv = mw.widget_quick_view

    # Open event tool of QuickView
    event_tool = qv.toolButton_event
    qtbot.mouseClick(event_tool, QtCore.Qt.LeftButton)

    # Test if checkbox is visible and checked by default
    assert qv.checkBox_image_background.isVisible(), "Checkbox is not visible"
    assert qv.checkBox_image_background.isChecked(), (
            "Checkbox is not checked by default")

    # Test if CheckBox is hidden for dataset with no feature "image_bg"

    slot_id2 = mw.pipeline.slot_ids[1]
    em2 = mw.block_matrix.get_widget(slot_id2, filt_id)

    # Activate
    qtbot.mouseClick(em2, QtCore.Qt.LeftButton)
    # Open dataset in QuickView
    qtbot.mouseClick(em2, QtCore.Qt.LeftButton, QtCore.Qt.ShiftModifier)

    qv2 = mw.widget_quick_view

    # Check if "Subtract Background"-CheckBox is hidden
    # note: event tool is still open from test above
    assert not qv2.checkBox_image_background.isVisible(), (
            " Subtract Background-Checkbox is visible for dataset "
            " that don't contain \"image_bg\"-feature"
            )
