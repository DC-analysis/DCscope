"""Test stats functionality"""
import pathlib
import tempfile
from unittest import mock

from PyQt6 import QtWidgets

from shapeout2.gui.main import ShapeOut2
from shapeout2 import session
from shapeout2.gui.compute.comp_stats import ComputeStatistics
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


def test_gui_stats_basic(qtbot):
    mw = ShapeOut2()
    qtbot.addWidget(mw)
    path = data_path / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])

    # create dialog manually
    dlg = ComputeStatistics(mw, pipeline=mw.pipeline)

    tdir = tempfile.mkdtemp("shapeout-test-stats_")
    tpath = pathlib.Path(tdir) / "out.tsv"

    # everything is autoselected, so we basically just click ok
    with mock.patch.object(QtWidgets.QFileDialog,
                           "getSaveFileName",
                           return_value=(str(tpath), None)):
        dlg.done(True)
    assert tpath.exists()
    lines = tpath.read_text(encoding="utf-8").split("\n")
    assert len(lines) == 6
    assert lines[0].count("Statistics Output")
    assert lines[1].count("Shape-Out")
    assert lines[3].count("Path")
    assert lines[3].count("Mean Absolute tilt of raw contour")
    assert lines[3].split("\t")[3].strip() == "Events"
    assert lines[4].split("\t")[3].strip() == "47"
