"""Test plot export"""
import os
import pathlib
import shutil
import tempfile

from PyQt6 import QtWidgets
import pytest
from shapeout2.gui.main import ShapeOut2
from shapeout2.gui import export
from shapeout2 import session


datapath = pathlib.Path(__file__).parent / "data"


@pytest.fixture(autouse=True)
def run_around_tests():
    # Code that will run before your test, for example:
    session.clear_session()
    # A test function will be run at this point
    yield
    # Code that will run after your test, for example:
    session.clear_session()


def test_export_single_plot(qtbot, monkeypatch):
    """Export of single plots not possible up until version 2.1.4"""
    spath = datapath / "version_2_1_0_basic.so2"

    mw = ShapeOut2()
    qtbot.addWidget(mw)

    mw.on_action_open(spath)

    # perform the export
    tmpd = tempfile.mkdtemp(suffix="", prefix="shapeout2_test_plot_export_")

    tmpf = os.path.join(tmpd, "no_suffix")
    assert not pathlib.Path(tmpf).exists()
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName",
                        lambda *args: (tmpf, ""))

    # create export dialog manually
    dlg = export.ExportPlot(mw, pipeline=mw.pipeline)

    # select a single plot to export
    plot_id = mw.pipeline.plot_ids[0]
    assert isinstance(plot_id, str)
    plot_index = dlg.comboBox_plot.findData(plot_id)
    assert plot_index > 0
    dlg.comboBox_plot.setCurrentIndex(plot_index)
    assert dlg.comboBox_plot.currentData() == plot_id

    dlg.export_plots()
    assert pathlib.Path(tmpf).with_suffix(".png").exists()

    # cleanup
    shutil.rmtree(tmpd, ignore_errors=True)
