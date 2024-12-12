"""Test of Quick View set functionalities"""
import pathlib

from PyQt6 import QtCore, QtWidgets

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
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton,
                     QtCore.Qt.KeyboardModifier.ShiftModifier)
    # did that work?
    assert mw.toolButton_quick_view.isChecked()

    # now clear the session (this raised the errror in #25)
    mw.on_action_clear()


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
    """https://github.com/ZELLMECHANIK-DRESDEN/ShapeOut2/issues/115

    When moving (with mouse drag-n-drop) a polygon filter in edit
    mode and then saving it, it is as if the translation is not
    detected. The polygon points are not updated.
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
    cb = fv._polygon_checkboxes[pf.unique_id]
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
    mw = ShapeOut2()
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
    mw = ShapeOut2()
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
    mw = ShapeOut2()
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
    mw = ShapeOut2()
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
    mw = ShapeOut2()
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
    mw = ShapeOut2()
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


def test_isoelasticity_lines_with_lut_selection(qtbot):
    """Test look-up table selection for isoelasticity lines"""

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
