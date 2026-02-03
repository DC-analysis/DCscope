"""Test of filter functionalities"""
import pathlib

from dcscope.gui.main import DCscope
from dcscope.gui.analysis import DlgSlotReorder
from dcscope import session
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


def test_filter_min_max_inf(qtbot):
    mw = DCscope()
    qtbot.addWidget(mw)

    # add 3 dataslots
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path, path, path])

    # change the slot names
    for ii, slot in enumerate(mw.pipeline.slots):
        slot.name = "slot numero {}".format(ii)
        mw.pp_mod_send.emit({"pipeline": {"slot_changed": slot.identifier}})

    # sanity checks
    assert mw.pipeline.slots[0].name == "slot numero 0"
    assert mw.pipeline.slots[1].name == "slot numero 1"
    assert mw.pipeline.slots[2].name == "slot numero 2"

    # create reorder dialog manually
    dlg = DlgSlotReorder(mw.pipeline, mw)
    dlg.pp_mod_send.connect(mw.pp_mod_send)
    # reorder plots
    dlg.listWidget.setCurrentRow(0)
    dlg.toolButton_down.clicked.emit()
    dlg.on_ok()

    # now check that reordering happened
    assert mw.pipeline.slots[0].name == "slot numero 1"
    assert mw.pipeline.slots[1].name == "slot numero 0"
    assert mw.pipeline.slots[2].name == "slot numero 2"
