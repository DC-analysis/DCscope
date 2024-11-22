import pathlib

from PyQt6 import QtCore

from shapeout2.gui.main import ShapeOut2
from shapeout2 import session
import pytest


data_path = pathlib.Path(__file__).parent / "data"


@pytest.fixture(autouse=True)
def run_around_tests():
    # Code that will run before your test, for example:
    session.clear_session()
    # A test function will be run at this point
    yield
    # Code that will run after your test, for example:
    session.clear_session()


def test_matrix_slots(qtbot):
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # add a dataslot
    path = pathlib.Path(__file__).parent / "data" / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])
    # add another one
    mw.add_dataslot(paths=[path])

    assert len(mw.pipeline.slot_ids) == 2, "we added those"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # activate a dataslot
    slot_id = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em = mw.block_matrix.get_widget(slot_id, filt_id)
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton)
    # did that work?
    assert mw.pipeline.is_element_active(slot_id, filt_id)
    slot_id2 = mw.pipeline.slot_ids[1]
    assert not mw.pipeline.is_element_active(slot_id2, filt_id)

    # remove a dataslot
    wd = mw.block_matrix.get_widget(slot_id=slot_id)
    wd.action_remove()
    assert not mw.pipeline.is_element_active(slot_id2, filt_id)


def test_matrix_slots_duplicate_issue_96(qtbot):
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # add a dataslot
    path = pathlib.Path(__file__).parent / "data" / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])

    assert len(mw.pipeline.slot_ids) == 1, "we added that"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # change the name of the dataset
    # go to analysis view
    qtbot.mouseClick(mw.toolButton_ana_view, QtCore.Qt.MouseButton.LeftButton)
    # go to the dataset tab
    av = mw.widget_ana_view
    qtbot.mouseClick(av.tab_slot, QtCore.Qt.MouseButton.LeftButton)
    # enter a name
    ws = av.widget_slot
    ws.lineEdit_name.setText("A Unique Name")
    qtbot.mouseClick(ws.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)

    # See if that worked
    assert mw.pipeline.slots[0].name == "A Unique Name"

    # Now duplicate the dataset
    swid = mw.block_matrix.get_widget(slot_id=mw.pipeline.slots[0].identifier)
    swid.action_duplicate()

    assert len(mw.pipeline.slot_ids) == 2, "initial + duplicate"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # make sure that slot name is the same
    assert mw.pipeline.slots[0].name == "A Unique Name"
    assert mw.pipeline.slots[1].name == "A Unique Name"
