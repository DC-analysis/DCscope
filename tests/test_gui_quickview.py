"""Test of Quick View set functionalities"""
import pathlib
import shutil

import dclab
import h5py
import numpy as np
import pytest
from PyQt6 import QtCore, QtWidgets

from dcscope import session
from dcscope.gui.main import DCscope

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
    main_window = DCscope()
    main_window.close()


def test_clear_session_issue_25(qtbot):
    """https://github.com/DC-analysis/DCscope/issues/25"""
    mw = DCscope()
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
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)
    # did that work?
    assert mw.toolButton_quick_view.isChecked()

    # now clear the session (this raised the errror in #25)
    mw.on_action_clear()


def test_duplicate_polygon_filter_issue_148(qtbot):
    """https://github.com/DC-analysis/DCscope/issues/148

    A duplicate polygon filter was created (that could not be deleted).
    """
    mw = DCscope()
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
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    em = mw.block_matrix.get_widget(slot_id, filt_id)
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton)

    # did that work?
    assert mw.toolButton_quick_view.isChecked()

    # Add a polygon filter
    assert len(dclab.PolygonFilter.instances) == 0
    qv = mw.widget_quick_view
    qtbot.mouseClick(qv.toolButton_poly, QtCore.Qt.MouseButton.LeftButton)
    qtbot.mouseClick(qv.pushButton_poly_create,
                     QtCore.Qt.MouseButton.LeftButton)
    # three positions (not sure how to do this with mouse clicks)
    points = [[22, 0.01],
              [30, 0.01],
              [30, 0.014],
              ]
    qv.widget_scatter.set_poly_points(points)
    qtbot.mouseClick(qv.pushButton_poly_save, QtCore.Qt.MouseButton.LeftButton)
    # did that work?
    assert len(dclab.PolygonFilter.instances) == 1
    pf = dclab.PolygonFilter.instances[0]
    assert np.allclose(pf.points, points)

    # Add the polygon filter to the first filter
    fe = mw.block_matrix.get_widget(filt_plot_id=filt_id)
    qtbot.mouseClick(fe.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)
    fv = mw.widget_ana_view.widget_filter
    mw.widget_ana_view.tabWidget.setCurrentWidget(
        mw.widget_ana_view.tab_filter)
    cb = fv._polygon_checkboxes[pf.unique_id]
    assert not cb.isChecked()
    assert cb.isEnabled()
    assert cb.isVisible()
    qtbot.mouseClick(cb, QtCore.Qt.MouseButton.LeftButton)
    assert cb.isChecked()
    qtbot.mouseClick(fv.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)
    # Did that work?
    ds = mw.pipeline.get_dataset(slot_index=0, filt_index=0,
                                 apply_filter=True)
    assert np.sum(ds.filter.all) == 15

    # To reproduce the bug, modify the polygon filter in QuickView, uncheck it
    # in the filter widget, and hit "Save" in QuickView.
    # Hit modify
    qv.comboBox_poly.setCurrentIndex(1)
    # Uncheck checkbox
    cb = fv._polygon_checkboxes[pf.unique_id]
    assert cb.isChecked()
    qtbot.mouseClick(cb, QtCore.Qt.MouseButton.LeftButton)
    qtbot.mouseClick(fv.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)
    assert not cb.isChecked()

    # Make sure we only have one polygon filter
    assert len(dclab.PolygonFilter.instances) == 1, "this worked before"
    # "Polygon Filter X" and "Choose..." selection
    assert qv.comboBox_poly.count() == 2

    # Now hit "Save" if it is visible (it should not be visible)
    if qv.pushButton_poly_save.isVisible():
        qtbot.mouseClick(qv.pushButton_poly_save,
                         QtCore.Qt.MouseButton.LeftButton)

    # Check again
    # "Polygon Filter X" and "Choose..." selection
    assert qv.comboBox_poly.count() == 2


@pytest.mark.filterwarnings('ignore::RuntimeWarning')  # 0-div in kde-methods
@pytest.mark.filterwarnings('ignore::dcscope.pipeline.core.'
                            + 'EmptyDatasetWarning')
def test_no_events_disable(qtbot):
    """When all events are removed, a message should be displayed"""
    mw = DCscope()
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
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    # Get Quick View instance
    qv = mw.widget_quick_view

    # This will display the "Hoppla!" message
    assert qv.label_noevents.isVisible()

    # Check the reverse
    qtbot.mouseClick(em2, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)
    assert not qv.label_noevents.isVisible()


def test_no_events_issue_37(qtbot):
    """https://github.com/DC-analysis/DCscope/issues/37

    "ValueError: zero-size array to reduction operation minimum
    which has no identity" when all events are filtered out.
    """
    mw = DCscope()
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
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton)  # activate
    # did that work?
    assert mw.pipeline.is_element_active(slot_id, filt_id)

    # filter away all events
    fe = mw.block_matrix.get_widget(filt_plot_id=filt_id)
    qtbot.mouseClick(fe.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)
    fv = mw.widget_ana_view.widget_filter
    mw.widget_ana_view.tabWidget.setCurrentWidget(
        mw.widget_ana_view.tab_filter)
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

    # open QuickView
    slot_id = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em = mw.block_matrix.get_widget(slot_id, filt_id)

    # this raised the error
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)
    mw.close()


def test_remove_dataset_h5py_error(qtbot):
    """Removing an activated dataset and activating Quick View fails

    Unhandled exception in DCscope version 2.0.1.post2:
    Traceback (most recent call last):
      File "/home/paul/repos/DCscope/dcscope/gui/main.py", line 235,
        in adopt_pipeline
        self.widget_quick_view.update_feature_choices()
      File "/home/paul/repos/DCscope/dcscope/gui/quick_view/qv_main.py",
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
    mw = DCscope()
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
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton)  # activate
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)
    # did that work?
    assert mw.pipeline.is_element_active(slot_id, filt_id)

    # close Quick View
    qtbot.mouseClick(mw.toolButton_quick_view,
                     QtCore.Qt.MouseButton.LeftButton)

    # now remove the dataset
    pw = mw.block_matrix.get_widget(slot_id=slot_id)
    pw.action_remove()

    # open Quick View
    qtbot.mouseClick(mw.toolButton_quick_view,
                     QtCore.Qt.MouseButton.LeftButton)
    mw.close()


def test_translate_polygon_filter_issue_115(qtbot):
    """https://github.com/DC-analysis/DCscope/issues/115

    When moving (with mouse drag-n-drop) a polygon filter in edit
    mode and then saving it, it is as if the translation is not
    detected. The polygon points are not updated.
    """
    mw = DCscope()
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
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    em = mw.block_matrix.get_widget(slot_id, filt_id)
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton)

    # did that work?
    assert mw.toolButton_quick_view.isChecked()

    # Add a polygon filter
    assert len(dclab.PolygonFilter.instances) == 0
    qv = mw.widget_quick_view
    qtbot.mouseClick(qv.toolButton_poly, QtCore.Qt.MouseButton.LeftButton)
    qtbot.mouseClick(qv.pushButton_poly_create,
                     QtCore.Qt.MouseButton.LeftButton)
    # three positions (not sure how to do this with mouse clicks)
    points = [[22, 0.01],
              [30, 0.01],
              [30, 0.014],
              ]
    qv.widget_scatter.set_poly_points(points)
    qtbot.mouseClick(qv.pushButton_poly_save, QtCore.Qt.MouseButton.LeftButton)
    # did that work?
    assert len(dclab.PolygonFilter.instances) == 1
    pf = dclab.PolygonFilter.instances[0]
    assert np.allclose(pf.points, points)

    # Add the polygon filter to the first filter
    fe = mw.block_matrix.get_widget(filt_plot_id=filt_id)
    qtbot.mouseClick(fe.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)
    fv = mw.widget_ana_view.widget_filter
    mw.widget_ana_view.tabWidget.setCurrentWidget(
        mw.widget_ana_view.tab_filter)
    cb = fv._polygon_checkboxes[pf.unique_id]
    assert not cb.isChecked()
    assert cb.isEnabled()
    assert cb.isVisible()
    qtbot.mouseClick(cb, QtCore.Qt.MouseButton.LeftButton)
    assert cb.isChecked()
    qtbot.mouseClick(fv.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)
    # did that work?
    ds = mw.pipeline.get_dataset(slot_index=0, filt_index=0,
                                 apply_filter=True)
    assert np.sum(ds.filter.all) == 15

    # Modify the polygon filter by translating it
    qv.comboBox_poly.setCurrentIndex(1)
    # do this without mouse interaction in this test
    qv.widget_scatter.poly_line_roi.translate(1, -.002, snap=False)
    qtbot.mouseClick(qv.pushButton_poly_save, QtCore.Qt.MouseButton.LeftButton)
    assert len(dclab.PolygonFilter.instances) == 1
    pf2 = dclab.PolygonFilter.instances[0]
    QtWidgets.QApplication.processEvents(
        QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 5000)
    points2 = [[23, 0.008],
               [31, 0.008],
               [31, 0.012],
               ]
    assert np.allclose(pf2.points, points2)
    assert pf is pf2
    # now the filter should be updated (this worked already)
    ds2 = mw.pipeline.get_dataset(slot_index=0, filt_index=0,
                                  apply_filter=True)
    assert np.sum(ds2.filter.all) == 8
    # but the plots were not updated in #26
    assert len(qv.widget_scatter.scatter.getData()[0]) == 8


def test_update_polygon_filter_issue_26(qtbot):
    """https://github.com/DC-analysis/DCscope/issues/26

    The recomputation of the filter ray was not triggered for some
    reason.
    """
    mw = DCscope()
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
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    em = mw.block_matrix.get_widget(slot_id, filt_id)
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton)

    # did that work?
    assert mw.toolButton_quick_view.isChecked()

    # Add a polygon filter
    assert len(dclab.PolygonFilter.instances) == 0
    qv = mw.widget_quick_view
    qtbot.mouseClick(qv.toolButton_poly, QtCore.Qt.MouseButton.LeftButton)
    qtbot.mouseClick(qv.pushButton_poly_create,
                     QtCore.Qt.MouseButton.LeftButton)
    # three positions (not sure how to do this with mouse clicks)
    points = [[22, 0.01],
              [30, 0.01],
              [30, 0.014],
              ]
    qv.widget_scatter.set_poly_points(points)
    qtbot.mouseClick(qv.pushButton_poly_save, QtCore.Qt.MouseButton.LeftButton)
    # did that work?
    assert len(dclab.PolygonFilter.instances) == 1
    pf = dclab.PolygonFilter.instances[0]
    assert np.allclose(pf.points, points)

    # Add the polygon filter to the first filter
    fe = mw.block_matrix.get_widget(filt_plot_id=filt_id)
    qtbot.mouseClick(fe.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)
    fv = mw.widget_ana_view.widget_filter
    mw.widget_ana_view.tabWidget.setCurrentWidget(
        mw.widget_ana_view.tab_filter)
    cb = fv._polygon_checkboxes[pf.unique_id]
    qtbot.mouseClick(cb, QtCore.Qt.MouseButton.LeftButton)
    assert cb.isChecked()
    qtbot.mouseClick(fv.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)
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
    qtbot.mouseClick(qv.pushButton_poly_save, QtCore.Qt.MouseButton.LeftButton)
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
    """https://github.com/DC-analysis/DCscope/issues/54

    Adding the "Subtract Background"-CheckBox
    """

    # Create main window
    mw = DCscope()
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
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton)
    # Open QuickView-window
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    # Check if QuickView-window is open
    assert mw.toolButton_quick_view.isChecked(), "Quickview not Open"

    # Get QuickView instance
    qv = mw.widget_quick_view

    # Open event tool of QuickView
    event_tool = qv.toolButton_event
    qtbot.mouseClick(event_tool, QtCore.Qt.MouseButton.LeftButton)

    # Test if checkbox is visible and checked by default
    assert qv.checkBox_image_background.isVisible(), "Checkbox is not visible"
    assert qv.checkBox_image_background.isChecked(), (
        "Checkbox is not checked by default")

    # Test if CheckBox is hidden for dataset with no feature "image_bg"

    slot_id2 = mw.pipeline.slot_ids[1]
    em2 = mw.block_matrix.get_widget(slot_id2, filt_id)

    # Activate
    qtbot.mouseClick(em2, QtCore.Qt.MouseButton.LeftButton)
    # Open dataset in QuickView
    qtbot.mouseClick(em2, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    qv2 = mw.widget_quick_view

    # Check if "Subtract Background"-CheckBox is hidden
    # note: event tool is still open from test above
    assert not qv2.checkBox_image_background.isVisible(), (
        " Subtract Background-Checkbox is visible for dataset "
        " that don't contain \"image_bg\"-feature"
    )


def test_auto_contrast(qtbot):
    """auto contrast should change the displayed image"""

    # Create main window
    mw = DCscope()
    qtbot.addWidget(mw)

    path = datapath / "calibration_beads_47.rtdc"

    mw.add_dataslot(paths=[path])

    assert len(mw.pipeline.slot_ids) == 1, "we added those"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # Test if CheckBox is visible for dataset
    # and if it is checked by default

    # Activate dataslots
    slot_id1 = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em1 = mw.block_matrix.get_widget(slot_id1, filt_id)

    # Activate
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton)
    # Open QuickView-window
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    # Check if QuickView-window is open
    assert mw.toolButton_quick_view.isChecked(), "Quickview not Open"

    # Get QuickView instance
    qv = mw.widget_quick_view

    # Open event tool of QuickView
    event_tool = qv.toolButton_event
    qtbot.mouseClick(event_tool, QtCore.Qt.MouseButton.LeftButton)

    # Test if checkbox is visible and checked by default
    assert qv.checkBox_image_contrast.isVisible(), "Checkbox is not visible"
    assert qv.checkBox_image_contrast.isChecked(), (
        "Checkbox is not checked by default")

    # Test if data changes when CheckBox is unchecked
    image_with_contrast = qv.imageView_image.getImageItem().image

    qtbot.mouseClick(qv.checkBox_image_contrast,
                     QtCore.Qt.MouseButton.LeftButton)
    assert not qv.checkBox_image_contrast.isChecked(), (
        "Checkbox should be unchecked")
    image_without_contrast = qv.imageView_image.getImageItem().image

    assert isinstance(image_with_contrast, np.ndarray)
    assert isinstance(image_without_contrast, np.ndarray)
    assert np.array_equal(image_with_contrast.shape,
                          image_without_contrast.shape)
    assert not np.array_equal(image_with_contrast, image_without_contrast)


def test_auto_contrast_qpi(qtbot):
    """auto contrast should change the displayed image"""

    # Create main window
    mw = DCscope()
    qtbot.addWidget(mw)

    path = datapath / "blood_rbc_qpi_data.rtdc"

    mw.add_dataslot(paths=[path])
    assert len(mw.pipeline.slot_ids) == 1, "we added those"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # Activate dataslots
    slot_id1 = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em1 = mw.block_matrix.get_widget(slot_id1, filt_id)

    # Activate
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton)
    # Open QuickView-window
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    # Check if QuickView-window is open
    assert mw.toolButton_quick_view.isChecked(), "Quickview not Open"

    # Get QuickView instance
    qv = mw.widget_quick_view

    # Open event tool of QuickView
    event_tool = qv.toolButton_event
    qtbot.mouseClick(event_tool, QtCore.Qt.MouseButton.LeftButton)

    # Test if checkbox is visible and checked by default
    assert qv.checkBox_image_contrast.isVisible(), "Checkbox is not visible"
    assert qv.checkBox_image_contrast.isChecked(), (
        "Checkbox is not checked by default")

    for view in [qv.imageView_image_amp, qv.imageView_image_pha]:
        # Test if data changes when CheckBox is unchecked
        qtbot.mouseClick(qv.checkBox_image_contrast,
                         QtCore.Qt.MouseButton.LeftButton)
        assert not qv.checkBox_image_contrast.isChecked(), (
            "Checkbox should be unchecked")
        image_without_contrast = view.getImageItem().image

        qtbot.mouseClick(qv.checkBox_image_contrast,
                         QtCore.Qt.MouseButton.LeftButton)
        assert qv.checkBox_image_contrast.isChecked(), (
            "Checkbox should be checked")
        image_with_contrast = view.getImageItem().image

        assert isinstance(image_with_contrast, np.ndarray)
        assert isinstance(image_without_contrast, np.ndarray)
        assert np.array_equal(image_with_contrast.shape,
                              image_without_contrast.shape)
        assert not np.array_equal(image_with_contrast, image_without_contrast)


def test_auto_contrast_vmin_vmax_qpi(qtbot):
    """auto contrast should change the vmin and vmax displayed to the user"""

    # Create main window
    mw = DCscope()
    qtbot.addWidget(mw)

    path = datapath / "blood_rbc_qpi_data.rtdc"

    mw.add_dataslot(paths=[path])
    assert len(mw.pipeline.slot_ids) == 1, "we added those"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # Activate dataslots
    slot_id1 = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em1 = mw.block_matrix.get_widget(slot_id1, filt_id)

    # Activate
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton)
    # Open QuickView-window
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    # Check if QuickView-window is open
    assert mw.toolButton_quick_view.isChecked(), "Quickview not Open"

    # Get QuickView instance
    qv = mw.widget_quick_view

    # Open event tool of QuickView
    event_tool = qv.toolButton_event
    qtbot.mouseClick(event_tool, QtCore.Qt.MouseButton.LeftButton)

    # Test if checkbox is visible and checked by default
    assert qv.checkBox_image_contrast.isVisible(), "Checkbox is not visible"
    assert qv.checkBox_image_contrast.isChecked(), (
        "Checkbox is not checked by default")
    # turn off image contour, because our design currently changes the levels
    qtbot.mouseClick(qv.checkBox_image_contour,
                     QtCore.Qt.MouseButton.LeftButton)
    assert not qv.checkBox_image_contour.isChecked(), (
        "Checkbox should be unchecked")

    # Test if data changes when CheckBox is unchecked
    qtbot.mouseClick(qv.checkBox_image_contrast,
                     QtCore.Qt.MouseButton.LeftButton)
    assert not qv.checkBox_image_contrast.isChecked(), (
        "Checkbox should be unchecked")
    assert qv.img_info["qpi_pha"]["kwargs"]["levels"] == (-3.14, +3.14)

    # apply auto-contrast
    qtbot.mouseClick(qv.checkBox_image_contrast,
                     QtCore.Qt.MouseButton.LeftButton)
    assert qv.checkBox_image_contrast.isChecked(), (
        "Checkbox should be checked")
    assert qv.img_info["qpi_pha"]["kwargs"]["levels"] == (-3.13, +3.13)


def test_contour_display(qtbot):
    """The contours should be a specific colour depending on the image"""

    # Create main window
    mw = DCscope()
    qtbot.addWidget(mw)

    path = datapath / "calibration_beads_47.rtdc"

    mw.add_dataslot(paths=[path])
    assert len(mw.pipeline.slot_ids) == 1, "we added those"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # Activate dataslots
    slot_id1 = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em1 = mw.block_matrix.get_widget(slot_id1, filt_id)

    # Activate
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton)
    # Open QuickView-window
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    # Check if QuickView-window is open
    assert mw.toolButton_quick_view.isChecked(), "Quickview not Open"

    # Get QuickView instance
    qv = mw.widget_quick_view

    # Open event tool of QuickView
    event_tool = qv.toolButton_event
    qtbot.mouseClick(event_tool, QtCore.Qt.MouseButton.LeftButton)

    # Test if checkbox is visible and checked by default
    assert qv.checkBox_image_contour.isVisible(), "Checkbox is not visible"
    assert qv.checkBox_image_contour.isChecked(), (
        "Checkbox is not checked by default")

    # Check contour data
    image_with_contour = qv.imageView_image.getImageItem().image

    qtbot.mouseClick(qv.checkBox_image_contour,
                     QtCore.Qt.MouseButton.LeftButton)
    assert not qv.checkBox_image_contour.isChecked(), (
        "Checkbox should be unchecked")
    image_without_contour = qv.imageView_image.getImageItem().image

    assert isinstance(image_with_contour, np.ndarray)
    assert isinstance(image_without_contour, np.ndarray)
    assert np.array_equal(image_with_contour.shape,
                          image_without_contour.shape)
    assert not np.array_equal(image_with_contour, image_without_contour)

    # show that the contour pixels are our "red": [0.7, 0, 0]
    ch_red = np.array([int(0.7 * 255), 0, 0])
    assert np.sum(np.all(image_with_contour == ch_red, axis=-1))
    assert not np.sum(np.all(image_without_contour == ch_red, axis=-1))


def test_contour_display_qpi_amp(qtbot):
    """The contours should be a specific colour depending on the image"""

    # Create main window
    mw = DCscope()
    qtbot.addWidget(mw)

    path = datapath / "blood_rbc_qpi_data.rtdc"

    mw.add_dataslot(paths=[path])
    assert len(mw.pipeline.slot_ids) == 1, "we added those"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # Activate dataslots
    slot_id1 = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em1 = mw.block_matrix.get_widget(slot_id1, filt_id)

    # Activate
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton)
    # Open QuickView-window
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    # Check if QuickView-window is open
    assert mw.toolButton_quick_view.isChecked(), "Quickview not Open"

    # Get QuickView instance
    qv = mw.widget_quick_view

    # Open event tool of QuickView
    event_tool = qv.toolButton_event
    qtbot.mouseClick(event_tool, QtCore.Qt.MouseButton.LeftButton)

    # Test if checkbox is visible and checked by default
    assert qv.checkBox_image_contour.isVisible(), "Checkbox is not visible"
    assert qv.checkBox_image_contour.isChecked(), (
        "Checkbox is not checked by default")

    # Check contour data qpi
    image_with_contour = qv.imageView_image_amp.getImageItem().image
    ch_red = [qv.imageView_image_amp.levelMax * 0.7,
              qv.imageView_image_amp.levelMin,
              qv.imageView_image_amp.levelMin]

    # the red pixel should be in the amp image
    assert not np.sum(np.all(image_with_contour == ch_red, axis=-1))

    # now uncheck the contour
    qtbot.mouseClick(qv.checkBox_image_contour,
                     QtCore.Qt.MouseButton.LeftButton)
    assert not qv.checkBox_image_contour.isChecked(), (
        "Checkbox should be unchecked")
    image_without_contour = qv.imageView_image_amp.getImageItem().image

    assert np.array_equal(image_with_contour.shape,
                          image_without_contour.shape)
    assert not np.array_equal(image_with_contour,
                              image_without_contour)

    # the red pixel should not be in the amp image
    assert not np.sum(np.all(image_without_contour == ch_red, axis=-1))


def test_contour_display_qpi_pha(qtbot):
    """The contours should be a specific colour depending on the image"""

    # Create main window
    mw = DCscope()
    qtbot.addWidget(mw)

    path = datapath / "blood_rbc_qpi_data.rtdc"

    mw.add_dataslot(paths=[path])
    assert len(mw.pipeline.slot_ids) == 1, "we added those"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # Activate dataslots
    slot_id1 = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em1 = mw.block_matrix.get_widget(slot_id1, filt_id)

    # Activate
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton)
    # Open QuickView-window
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    # Check if QuickView-window is open
    assert mw.toolButton_quick_view.isChecked(), "Quickview not Open"

    # Get QuickView instance
    qv = mw.widget_quick_view

    # Open event tool of QuickView
    event_tool = qv.toolButton_event
    qtbot.mouseClick(event_tool, QtCore.Qt.MouseButton.LeftButton)

    # Test if checkbox is visible and checked by default
    assert qv.checkBox_image_contour.isVisible(), "Checkbox is not visible"
    assert qv.checkBox_image_contour.isChecked(), (
        "Checkbox is not checked by default")

    # Check contour data qpi_pha, it is not RGB
    image_with_contour = qv.imageView_image_pha.getImageItem().image
    lowest_cmap_val = qv.imageView_image_pha.levelMin

    # the cmap's lowest value changed to black, and we use this value
    #  for the contour
    assert not np.sum(np.all(image_with_contour == lowest_cmap_val, axis=-1))

    # now uncheck the contour
    qtbot.mouseClick(qv.checkBox_image_contour,
                     QtCore.Qt.MouseButton.LeftButton)
    assert not qv.checkBox_image_contour.isChecked(), (
        "Checkbox should be unchecked")
    image_without_contour = qv.imageView_image_pha.getImageItem().image

    assert np.array_equal(image_with_contour.shape,
                          image_without_contour.shape)
    assert not np.array_equal(image_with_contour,
                              image_without_contour)
    # there is one pixel actually set at the lowest value during auto-contrast
    assert not np.sum(np.all(
        image_without_contour == lowest_cmap_val, axis=-1))


def test_image_without_mask_data(qtbot, tmp_path):
    """Make sure image is plotted when there is no mask data"""
    path_in = tmp_path / "test.rtdc"
    shutil.copy2(datapath / "calibration_beads_47.rtdc", path_in)
    with h5py.File(path_in, "a") as h5:
        del h5["events/contour"]
        del h5["events/mask"]

    # Create main window
    mw = DCscope()
    qtbot.addWidget(mw)

    mw.add_dataslot(paths=[path_in])

    assert len(mw.pipeline.slot_ids) == 1, "we added those"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # Test if CheckBox is visible for dataset
    # and if it is checked by default

    # Activate dataslots
    slot_id1 = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em1 = mw.block_matrix.get_widget(slot_id1, filt_id)

    # Activate
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton)
    # Open QuickView-window
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    # Check if QuickView-window is open
    assert mw.toolButton_quick_view.isChecked(), "Quickview not Open"

    # Get QuickView instance
    qv = mw.widget_quick_view

    # Open event tool of QuickView
    event_tool = qv.toolButton_event
    qtbot.mouseClick(event_tool, QtCore.Qt.MouseButton.LeftButton)

    # Test if data changes when CheckBox is unchecked
    image_with_contrast = qv.imageView_image.getImageItem().image

    assert np.any(image_with_contrast)


def test_isoelasticity_lines_with_lut_selection(qtbot):
    """Test look-up table selection for isoelasticity lines"""

    mw = DCscope()
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
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    em = mw.block_matrix.get_widget(slot_id, filt_id)
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton)

    # did that work?
    assert mw.toolButton_quick_view.isChecked()

    # Get QuickView instance
    qv = mw.widget_quick_view

    # Open plot (settings) tool of QuickView
    plot_tool = qv.toolButton_settings
    qtbot.mouseClick(plot_tool, QtCore.Qt.MouseButton.LeftButton)

    # Test if checkbox is visible and checked by default
    assert qv.checkBox_isoelastics.isChecked(), "Checked by default"
    # Test if default look-up table is selected
    assert qv.comboBox_lut.currentData() == "LE-2D-FEM-19", "Check default LUT"

    # Try changing look-up table
    qv.comboBox_lut.setCurrentIndex(qv.comboBox_lut.findData("HE-2D-FEM-22"))
    # Apply changes by clicking on 'Apply'
    qtbot.mouseClick(qv.toolButton_apply, QtCore.Qt.MouseButton.LeftButton)

    # did that work?
    assert qv.comboBox_lut.currentData() == "HE-2D-FEM-22"


def test_select_x_y_axis_based_on_availiable_feature_name_issue_206(qtbot):
    """
    Test select X-axis and Y-axis based on feature name that is available
    in both datasets.
    """

    mw = DCscope()
    qtbot.addWidget(mw)

    # add dataslots
    path1 = datapath / "calibration_beads_47.rtdc"
    path2 = datapath / "blood_rbc_leukocytes.rtdc"
    mw.add_dataslot(paths=[path1, path2])

    assert len(mw.pipeline.slot_ids) == 2, "we added that"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # Get the slot_id of the first data slot
    slot_id1 = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]

    # activate dataslot-1
    em1 = mw.block_matrix.get_widget(slot_id1, filt_id)
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    em1 = mw.block_matrix.get_widget(slot_id1, filt_id)
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton)

    # did that work?
    assert mw.toolButton_quick_view.isChecked()

    # Get QuickView instance
    qv = mw.widget_quick_view

    # Open plot (settings) tool of QuickView
    plot_tool = qv.toolButton_settings
    qtbot.mouseClick(plot_tool, QtCore.Qt.MouseButton.LeftButton)

    # Set X-axis and Y-axis features in data slot 1
    qv.comboBox_x.setCurrentIndex(qv.comboBox_x.findData("area_um"))
    qv.comboBox_y.setCurrentIndex(qv.comboBox_y.findData("frame"))

    # Check if X-axis and Y-axis features are set correctly
    assert qv.comboBox_x.currentData() == "area_um", "Check manual selection"
    assert qv.comboBox_y.currentData() == "frame", "Check manual selection"

    # Get the slot_id the second data slot
    slot_id2 = mw.pipeline.slot_ids[1]
    # Activate data slot-2
    em2 = mw.block_matrix.get_widget(slot_id2, filt_id)
    qtbot.mouseClick(em2, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    em2 = mw.block_matrix.get_widget(slot_id2, filt_id)
    qtbot.mouseClick(em2, QtCore.Qt.MouseButton.LeftButton)

    # Check if X-axis and Y-axis features are still set correctly
    assert qv.comboBox_x.currentData() == "area_um", "Check manual selection"
    assert qv.comboBox_y.currentData() == "frame", "Check manual selection"


def test_select_x_y_axis_based_on_unavailable_feature_name_issue_206(qtbot):
    """
    Test select X-axis and Y-axis based on feature name that is not available
    in both datasets.
    """

    mw = DCscope()
    qtbot.addWidget(mw)

    # add dataslots
    path1 = datapath / "calibration_beads_47.rtdc"
    path2 = datapath / "blood_rbc_leukocytes.rtdc"
    mw.add_dataslot(paths=[path1, path2])

    assert len(mw.pipeline.slot_ids) == 2, "we added that"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # Get the slot_id of the first data slot
    slot_id1 = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]

    # activate dataslot-1
    em1 = mw.block_matrix.get_widget(slot_id1, filt_id)
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    em1 = mw.block_matrix.get_widget(slot_id1, filt_id)
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton)

    # did that work?
    assert mw.toolButton_quick_view.isChecked()

    # Get QuickView instance
    qv = mw.widget_quick_view

    # Open plot (settings) tool of QuickView
    plot_tool = qv.toolButton_settings
    qtbot.mouseClick(plot_tool, QtCore.Qt.MouseButton.LeftButton)

    # Set X-axis and Y-axis features in data slot 1
    qv.comboBox_x.setCurrentIndex(qv.comboBox_x.findData("area_um"))
    # Set the feature that is not available in dataset-2
    qv.comboBox_y.setCurrentIndex(qv.comboBox_y.findData("fl3_width"))

    # Check if X-axis and Y-axis features are set correctly
    assert qv.comboBox_x.currentData() == "area_um", "Check manual selection"
    assert qv.comboBox_y.currentData() == "fl3_width", "Check manual selection"

    # Get the slot_id the second data slot
    slot_id2 = mw.pipeline.slot_ids[1]
    # Activate data slot-2
    em2 = mw.block_matrix.get_widget(slot_id2, filt_id)
    qtbot.mouseClick(em2, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    em2 = mw.block_matrix.get_widget(slot_id2, filt_id)
    qtbot.mouseClick(em2, QtCore.Qt.MouseButton.LeftButton)

    # Check if X-axis and Y-axis features are still set correctly
    assert qv.comboBox_x.currentData() == "area_um", "Check manual selection"
    # Since the feature is not available in dataset-2, it should be set
    # to "deform" (first option in default choice)
    assert qv.comboBox_y.currentData() == "deform", "Check manual selection"


def test_cache_selected_event_using_dataslot_issue_196(qtbot):
    """Event selection should be cached when switching between datasets"""

    mw = DCscope()
    qtbot.addWidget(mw)

    # add dataslots
    path1 = datapath / "calibration_beads_47.rtdc"
    path2 = datapath / "blood_rbc_qpi_data.rtdc"
    mw.add_dataslot(paths=[path1, path2])

    assert len(mw.pipeline.slot_ids) == 2, "we added that"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # Get the slot_id of the first data slot
    slot_id1 = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]

    # activate dataslot-1
    em1 = mw.block_matrix.get_widget(slot_id1, filt_id)
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    em1 = mw.block_matrix.get_widget(slot_id1, filt_id)
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton)

    # did that work?
    assert mw.toolButton_quick_view.isChecked()

    # selected events
    slot1_event = 3
    slot2_event = 6

    # Get QuickView instance
    qv = mw.widget_quick_view

    # Open plot (settings) tool of QuickView
    plot_tool = qv.toolButton_settings
    qtbot.mouseClick(plot_tool, QtCore.Qt.MouseButton.LeftButton)

    # select an event index in slot1
    qv.show_event(slot1_event)

    # check whether event 4 is saved in cache dict
    assert qv._dataset_event_plot_indices_cache["Dataslot_1"] == slot1_event

    # Do we have the correct event shown?
    assert qv.spinBox_event.value()-1 == slot1_event

    # Get the slot_id the second data slot
    slot_id2 = mw.pipeline.slot_ids[1]
    # Activate data slot-2
    em2 = mw.block_matrix.get_widget(slot_id2, filt_id)
    qtbot.mouseClick(em2, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    em2 = mw.block_matrix.get_widget(slot_id2, filt_id)
    qtbot.mouseClick(em2, QtCore.Qt.MouseButton.LeftButton)

    # select an event index in slot2
    qv.show_event(slot2_event)

    # Do we have the correct event shown?
    assert qv.spinBox_event.value()-1 == slot2_event

    # check whether slot2_event is exists in cache dict
    assert qv._dataset_event_plot_indices_cache["Dataslot_2"] == slot2_event

    # now switch back to slot1 and check event
    em1 = mw.block_matrix.get_widget(slot_id1, filt_id)
    qtbot.mouseClick(em1, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)

    em1 = mw.block_matrix.get_widget(slot_id1, filt_id)
    qtbot.mouseClick(em2, QtCore.Qt.MouseButton.LeftButton)

    # Do we still have the correct event shown?
    assert qv.spinBox_event.value()-1 == slot1_event

    # check whether slot1_event is still exists in cache dict
    assert qv._dataset_event_plot_indices_cache["Dataslot_1"] == slot1_event
