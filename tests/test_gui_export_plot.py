"""Test plot export"""
import os
import pathlib
import shutil
import tempfile

from PyQt6 import QtWidgets
import pytest
from dcscope.gui import export
from dcscope import session

import conftest  # noqa: F401


datapath = pathlib.Path(__file__).parent / "data"


@pytest.fixture(autouse=True)
def run_around_tests():
    # Code that will run before your test, for example:
    session.clear_session()
    # A test function will be run at this point
    yield
    # Code that will run after your test, for example:
    session.clear_session()


# https://github.com/pyqtgraph/pyqtgraph/pull/3458
# @pytest.mark.parametrize("export_format", ["png", "svg", None])
@pytest.mark.parametrize("export_format", ["png", None])
def test_export_single_plot_png(qtbot, monkeypatch, mw, export_format):
    """Basic export of a single subplot as PNG/SVG"""
    spath = datapath / "version_2_1_0_basic.so2"

    qtbot.addWidget(mw)

    mw.on_action_open(spath)

    # perform the export
    tmpd = tempfile.mkdtemp(suffix="", prefix="dcscope_test_plot_export_")

    tmpf = os.path.join(tmpd, "no_suffix")
    assert not pathlib.Path(tmpf).exists()
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName",
                        lambda *args: (tmpf, ""))

    # create export dialog manually
    dlg = export.ExportPlot(mw, pipeline=mw.pipeline)

    if export_format is not None:
        dlg.ui.comboBox_fmt.setCurrentIndex(
            dlg.ui.comboBox_fmt.findData(export_format))

    # select a single plot to export
    plot_id = mw.pipeline.plot_ids[0]
    assert isinstance(plot_id, str)
    plot_index = dlg.ui.comboBox_plot.findData(plot_id)
    assert plot_index > 0
    dlg.ui.comboBox_plot.setCurrentIndex(plot_index)
    assert dlg.ui.comboBox_plot.currentData() == plot_id

    dlg.export_plots()

    if export_format is None:
        # default is PNG
        suffix = ".png"
    else:
        suffix = f".{export_format}"
    assert pathlib.Path(tmpf).with_suffix(suffix).exists()

    # cleanup
    shutil.rmtree(tmpd, ignore_errors=True)
