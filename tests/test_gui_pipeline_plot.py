import logging
import pathlib

import dclab
from PyQt6 import QtWidgets

from dcscope import session
from dcscope.gui import pipeline_plot

import conftest  # noqa: F401


datapath = pathlib.Path(__file__).parent / "data"


def test_get_hash_flag():
    rtdc_paths = datapath.glob("*.rtdc")

    assert rtdc_paths

    hash_set = set()
    rtdc_ds_list = []
    expected = []
    for path in rtdc_paths:
        ds = dclab.new_dataset(path)
        # get the hash flag
        pipe_config = ds.config.get("pipeline", {})
        dcnum_hash = pipe_config.get("dcnum hash", None)
        hash_set.add(dcnum_hash)
        expected.append(f"Pipeline {dcnum_hash[:4]}" if dcnum_hash else None)
        rtdc_ds_list.append(ds)

    assert len(hash_set) == 2

    for ds, exp in zip(rtdc_ds_list, expected):
        result = pipeline_plot.get_hash_flag(hash_set, ds)
        assert result == exp


def test_get_hash_flag_datasets_without_hash():
    rtdc_paths = [
        datapath / "artificial_with_image_bg.rtdc",  # No hash
        datapath / "blood_rbc_leukocytes.rtdc",  # No hash
        datapath / "blood_rbc_qpi_data.rtdc",  # No hash
    ]

    assert len(rtdc_paths) == 3

    hash_set = set()
    rtdc_ds_list = []
    expected = []
    for path in rtdc_paths:
        ds = dclab.new_dataset(path)
        # get the hash flag
        pipe_config = ds.config.get("pipeline", {})
        dcnum_hash = pipe_config.get("dcnum hash", None)
        hash_set.add(dcnum_hash)
        expected.append(f"Pipeline {dcnum_hash[:4]}" if dcnum_hash else None)
        rtdc_ds_list.append(ds)

    assert len(hash_set) == 1
    for ds in rtdc_ds_list:
        result = pipeline_plot.get_hash_flag(hash_set, ds)
        assert result is None


def test_get_hash_flag_dataset_with_hash():
    rtdc_paths = [
        datapath / "artificial_with_image_bg.rtdc",  # No hash
        datapath / "blood_rbc_leukocytes.rtdc",  # No hash
        datapath / "naiad-capture_blood_pipeline.rtdc",  # with hash
    ]

    assert len(rtdc_paths) == 3
    hash_set = set()
    rtdc_ds_list = []
    expected = []
    for path in rtdc_paths:
        ds = dclab.new_dataset(path)
        # get the hash flag
        pipe_config = ds.config.get("pipeline", {})
        dcnum_hash = pipe_config.get("dcnum hash", None)
        hash_set.add(dcnum_hash)
        expected.append(f"Pipeline {dcnum_hash[:4]}" if dcnum_hash else None)
        rtdc_ds_list.append(ds)

    assert len(hash_set) == 2
    results = []
    for ds in rtdc_ds_list:
        result = pipeline_plot.get_hash_flag(hash_set, ds)
        results.append(result)

    assert len(results) == 3, "results length should be length of rtdc_paths"

    assert results[0] is None
    assert results[1] is None
    assert results[2] == "Pipeline 1d01"


def test_task_error_only_shown_for_own_plot(
        qtbot, mw, monkeypatch, caplog):
    """Errors of plotting tasks are only shown by the plot they belong to"""
    session.clear_session()
    shown = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "critical",
        lambda parent, title, text, *args, **kwargs: shown.append(text))
    qtbot.addWidget(mw)
    mw.add_dataslot(paths=[datapath / "calibration_beads_47.rtdc"])
    plot_id = mw.add_plot()
    pp = mw.subwindows_plots[plot_id].widget()

    # error of a task that belongs to another plot (handled by that plot)
    task_other = {"kwargs": {"plot_state": {"identifier": "plot:other"}}}
    with caplog.at_level(logging.ERROR, logger="dcscope.gui.pipeline_plot"):
        pp.on_task_error(task_other, ValueError("other plot"))
    assert not shown
    assert "other plot" not in caplog.text

    # error with non-string arguments (raised a TypeError before)
    task_own = {"kwargs": {"plot_state": {"identifier": plot_id}}}
    with caplog.at_level(logging.ERROR, logger="dcscope.gui.pipeline_plot"):
        pp.on_task_error(task_own, KeyError(5))
    assert shown == ["KeyError: 5"]
    assert "KeyError: 5" in caplog.text

    # plot removed from the pipeline (e.g. session cleared): only logged
    mw.pipeline.reset()
    with caplog.at_level(logging.ERROR, logger="dcscope.gui.pipeline_plot"):
        pp.on_task_error(task_own, ValueError("removed"))
    assert len(shown) == 1
    assert "ValueError: removed" in caplog.text
    session.clear_session()
