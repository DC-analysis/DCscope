"""Test stats functionality"""
import pathlib
import shutil
import tempfile
from unittest import mock

import dclab
import numpy as np
from PyQt6 import QtCore, QtWidgets

from dcscope import session
from dcscope.gui.compute import comp_stats
from dcscope.gui.compute.comp_stats import ComputeStatistics
import pytest

import conftest  # noqa: F401


data_path = pathlib.Path(__file__).parent / "data"


@pytest.fixture(autouse=True)
def run_around_tests():
    # Code that will run before your test, for example:
    session.clear_session()
    # A test function will be run at this point
    yield
    # Code that will run after your test, for example:
    session.clear_session()


def test_gui_stats_basic(qtbot, mw):
    qtbot.addWidget(mw)
    path = data_path / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])

    # create dialog manually
    dlg = ComputeStatistics(mw, pipeline=mw.pipeline)

    tdir = tempfile.mkdtemp("dcscope-test-stats_")
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
    assert lines[1].count("DCscope")
    assert lines[3].count("Path")
    assert lines[3].count("Mean Absolute tilt of raw contour")
    assert lines[3].split("\t")[3].strip() == "Events"
    assert lines[4].split("\t")[3].strip() == "47"


def make_ml_datasets(tmp_path):
    """Create two datasets with ml_score features in a directory tree"""
    path_in = data_path / "calibration_beads_47.rtdc"
    path_a = tmp_path / "a.rtdc"
    path_b = tmp_path / "sub" / "b.rtdc"
    path_b.parent.mkdir()
    for pp, feats in [(path_a, ["ml_score_abc"]),
                      (path_b, ["ml_score_abc", "ml_score_xyz"])]:
        shutil.copy2(path_in, pp)
        with dclab.RTDCWriter(pp) as hw:
            for feat in feats:
                hw.store_feature(feat, np.linspace(0, 1, 47))
    # a file that cannot be opened
    (tmp_path / "broken.rtdc").write_text("not an HDF5 file")
    return path_a, path_b


def test_find_ml_score_features(tmp_path):
    make_ml_datasets(tmp_path)
    assert comp_stats.find_ml_score_features(tmp_path) == [
        "ml_score_abc", "ml_score_xyz"]
    # abort after the first file (files are sorted)
    assert comp_stats.find_ml_score_features(
        tmp_path, callback=lambda ii, size: True) == ["ml_score_abc"]


def test_gui_stats_folder_ml_score_issue_108(qtbot, mw, tmp_path):
    """ml_score features of datasets in a directory (#108)"""
    qtbot.addWidget(mw)
    make_ml_datasets(tmp_path)

    with mock.patch.object(QtWidgets.QFileDialog,
                           "getExistingDirectory",
                           return_value=str(tmp_path)):
        # no datasets in the pipeline, so the directory mode is used
        dlg = ComputeStatistics(mw, pipeline=mw.pipeline)
    qtbot.addWidget(dlg)
    assert dlg.path == str(tmp_path)
    assert "ml_score_abc" not in dlg.features

    # select only one feature
    dlg.ui.bulklist_features.on_select_none()
    lw = dlg.ui.bulklist_features.ui.listWidget
    for ii in range(lw.count()):
        if lw.item(ii).data(101) == "deform":
            lw.item(ii).setCheckState(QtCore.Qt.CheckState.Checked)

    qtbot.mouseClick(dlg.ui.pushButton_ml_search,
                     QtCore.Qt.MouseButton.LeftButton)
    assert dlg.features_ml == ["ml_score_abc", "ml_score_xyz"]
    # the selection is kept and the ml_score features are selected
    assert dlg.ui.bulklist_features.get_selection() == [
        "deform", "ml_score_abc", "ml_score_xyz"]

    tpath = tmp_path / "out.tsv"
    with mock.patch.object(QtWidgets.QFileDialog,
                           "getSaveFileName",
                           return_value=(str(tpath), None)), \
            mock.patch.object(QtWidgets.QMessageBox, "warning") as warn:
        dlg.done(True)
    # the broken file is skipped and the user is informed
    warn.assert_called_once()
    assert warn.call_args.args[2].count("broken.rtdc")
    lines = tpath.read_text(encoding="utf-8").split("\n")
    header = lines[3].split("\t")
    assert any(h.count("ML score ABC") for h in header)
    assert any(h.count("ML score XYZ") for h in header)
    # two datasets and a trailing empty line
    assert len(lines) == 4 + 2 + 1
    assert not "".join(lines).count("broken.rtdc")


def test_gui_stats_folder_only_broken_files(qtbot, mw, tmp_path):
    """No statistics file is written if no dataset can be read"""
    qtbot.addWidget(mw)
    (tmp_path / "broken.rtdc").write_text("not an HDF5 file")
    with mock.patch.object(QtWidgets.QFileDialog,
                           "getExistingDirectory",
                           return_value=str(tmp_path)):
        dlg = ComputeStatistics(mw, pipeline=mw.pipeline)
    qtbot.addWidget(dlg)
    tpath = tmp_path / "out.tsv"
    with mock.patch.object(QtWidgets.QFileDialog,
                           "getSaveFileName",
                           return_value=(str(tpath), None)), \
            mock.patch.object(QtWidgets.QMessageBox, "warning") as warn:
        assert not dlg.export_statistics()
    assert warn.call_count == 2
    assert not tpath.exists()


def test_gui_stats_session_unreadable_dataset_issue_208(qtbot, mw, tmp_path):
    """Datasets whose data cannot be read are skipped and named (#208)"""
    qtbot.addWidget(mw)
    path = data_path / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path, path])
    mw.pipeline.slots[1].name = "broken slot"

    get_dataset = mw.pipeline.get_dataset

    def get_dataset_broken(slot_index, *args, **kwargs):
        if slot_index == 1:
            # e.g. corrupted file or connection to DCOR lost
            raise OSError("Can't synchronously read data (data error "
                          "detected by Fletcher32 checksum)")
        return get_dataset(slot_index, *args, **kwargs)

    dlg = ComputeStatistics(mw, pipeline=mw.pipeline)
    qtbot.addWidget(dlg)
    tpath = tmp_path / "out.tsv"
    with mock.patch.object(mw.pipeline, "get_dataset",
                           side_effect=get_dataset_broken), \
            mock.patch.object(QtWidgets.QFileDialog,
                              "getSaveFileName",
                              return_value=(str(tpath), None)), \
            mock.patch.object(QtWidgets.QMessageBox, "warning") as warn:
        assert dlg.export_statistics()
    warn.assert_called_once()
    text = warn.call_args.args[2]
    assert text.count("broken slot")
    assert text.count("Fletcher32")
    lines = tpath.read_text(encoding="utf-8").split("\n")
    # one dataset and a trailing empty line
    assert len(lines) == 4 + 1 + 1
    assert not "".join(lines).count("broken slot")
