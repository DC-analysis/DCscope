"""Test the Dataset tab of the Analysis View"""
import pathlib

import pytest

from dcscope import session

import conftest  # noqa: F401


datapath = pathlib.Path(__file__).parent / "data"


@pytest.fixture(autouse=True)
def run_around_tests():
    session.clear_session()
    yield
    session.clear_session()


def test_crosstalk_apply_to_all_issue_198(qtbot, mw):
    """Apply the crosstalk values to all datasets (#198)"""
    qtbot.addWidget(mw)
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path, path, path])
    mw.widget_ana_view.ui.tabWidget.setCurrentWidget(
        mw.widget_ana_view.ui.tab_slot)
    wsl = mw.widget_ana_view.ui.widget_slot

    wsl.ui.doubleSpinBox_ct12.setValue(0.1)
    wsl.ui.doubleSpinBox_ct31.setValue(0.25)
    # this change is not applied with "Apply crosstalk to all datasets"
    wsl.ui.lineEdit_name.setText("new name")
    # (the Analysis View is not shown, so we cannot use qtbot.mouseClick)
    wsl.ui.pushButton_ct_apply_all.click()

    for ii, slot in enumerate(mw.pipeline.slots):
        state = slot.__getstate__()
        assert state["crosstalk"]["crosstalk fl12"] == 0.1
        assert state["crosstalk"]["crosstalk fl31"] == 0.25
        assert state["crosstalk"]["crosstalk fl13"] == 0
        assert state["name"] != "new name"
        # the values are used for computing the corrected fluorescence
        ds = mw.pipeline.get_dataset(ii)
        assert ds.config["calculation"]["crosstalk fl12"] == 0.1
        assert ds.config["calculation"]["crosstalk fl31"] == 0.25
