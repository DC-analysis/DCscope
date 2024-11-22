"""Test data export"""
import pathlib
import tempfile
from unittest import mock

import dclab
import numpy as np
from PyQt6 import QtCore, QtWidgets
import pytest
from shapeout2.gui.main import ShapeOut2
from shapeout2.gui import export
from shapeout2 import session


data_path = pathlib.Path(__file__).parent / "data"


@pytest.fixture(autouse=True)
def run_around_tests():
    # Code that will run before your test, for example:
    session.clear_session()
    # A test function will be run at this point
    yield
    # Code that will run after your test, for example:
    session.clear_session()


def test_export_datasets_rtdc(qtbot):
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # add 3 dataslots
    path = data_path / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path, path, path])

    # perform the export
    tmpd = tempfile.mkdtemp(prefix="shapeout2_test_data_export_")
    mw.settings.setValue("paths/export data", tmpd)

    # create export dialog manually (asks user for directory)
    dlg = export.ExportData(mw, pipeline=mw.pipeline)

    # Everything is set-up already (.rtdc export, innate features
    # selected). Click OK.
    buttons = dlg.buttonBox.buttons()
    qtbot.mouseClick(buttons[0], QtCore.Qt.MouseButton.LeftButton)

    # make sure we have three .rtdc files
    assert len(list(pathlib.Path(tmpd).glob("*.rtdc"))) == 3


def test_export_datasets_rtdc_no_override(qtbot):
    """Shape-Out should not override existing files during export"""
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # add 3 dataslots
    path = data_path / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path, path, path])

    # perform the export
    tmpd = tempfile.mkdtemp(prefix="shapeout2_test_data_export_")
    mw.settings.setValue("paths/export data", tmpd)

    for _ in range(2):
        # create export dialog manually (asks user for directory)
        dlg = export.ExportData(mw, pipeline=mw.pipeline)

        # Everything is set-up already (.rtdc export, all features
        # selected).
        # Click OK.
        buttons = dlg.buttonBox.buttons()
        qtbot.mouseClick(buttons[0], QtCore.Qt.MouseButton.LeftButton)

    # make sure we have six .rtdc files, because we exported twice
    assert len(list(pathlib.Path(tmpd).glob("*.rtdc"))) == 6


@pytest.mark.filterwarnings(
    "ignore::dclab.features.emodulus.YoungsModulusLookupTableExceededWarning")
def test_export_datasets_rtdc_emodulus_only_in_one_issue_80(qtbot):
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # add 3 dataslots
    path = data_path / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path, path, path])

    # set metadata for Young's modulus only in one slot
    wsl = mw.widget_ana_view.widget_slot
    wsl.doubleSpinBox_temp.setValue(23)
    qtbot.mouseClick(wsl.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)
    # make sure that worked
    ds0 = mw.pipeline.slots[0].get_dataset()
    assert "emodulus" in ds0

    # perform the export
    tmpd = tempfile.mkdtemp(prefix="shapeout2_test_data_export_")
    mw.settings.setValue("paths/export data", tmpd)

    with mock.patch.object(QtWidgets.QMessageBox, "warning") as mwarn:
        # create export dialog manually (asks user for directory)
        dlg = export.ExportData(mw, pipeline=mw.pipeline)
        # select all features
        qtbot.mouseClick(dlg.bulklist_features.toolButton_all,
                         QtCore.Qt.MouseButton.LeftButton)

        # Everything is set-up already
        # (.rtdc export, innate features selected).
        # Click OK.
        buttons = dlg.buttonBox.buttons()
        qtbot.mouseClick(buttons[0], QtCore.Qt.MouseButton.LeftButton)

        # make sure that we got two warning messages
        assert mwarn.call_count == 2

    # make sure we have three .rtdc files
    exported = sorted(list(pathlib.Path(tmpd).glob("*.rtdc")))
    assert len(exported) == 3
    # the first exported file should have Young's modulus
    with dclab.new_dataset(exported[0]) as ds:
        assert "emodulus" in ds
    with dclab.new_dataset(exported[1]) as ds:
        assert "emodulus" not in ds
    with dclab.new_dataset(exported[2]) as ds:
        assert "emodulus" not in ds


def test_export_datasets_rtdc_logs(qtbot):
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # add 1 dataslots
    path = data_path / "cytoshot_blood.rtdc"
    slot_ids = mw.add_dataslot(paths=[path])

    # add a filter and activate it
    filt_id = mw.add_filter()
    filt = mw.pipeline.get_filter(filt_id)
    filt.limit_events = [True, 3]
    mw.pipeline.set_element_active(slot_ids[0], filt_id)

    # perform the export
    tmpd = tempfile.mkdtemp(prefix="shapeout2_test_data_export_")
    mw.settings.setValue("paths/export data", tmpd)

    # create export dialog manually (asks user for directory)
    dlg = export.ExportData(mw, pipeline=mw.pipeline)

    # Everything is set-up already (.rtdc export, innate features selected).
    # Click OK.
    buttons = dlg.buttonBox.buttons()
    qtbot.mouseClick(buttons[0], QtCore.Qt.MouseButton.LeftButton)

    # make sure we have one .rtdc file
    exported = list(pathlib.Path(tmpd).glob("*.rtdc"))
    assert len(exported) == 1

    # make sure that file has three events and contains the logs and tables
    with dclab.new_dataset(exported[0]) as ds:
        assert len(ds) == 3
        assert len(ds.logs) == 6
        assert "src_cytoshot-acquisition" in ds.logs
        assert np.allclose(
            ds.tables["src_cytoshot_monitor"]["brightness"][0],
            146.22099383,
            atol=0,
            rtol=1e-10)


@pytest.mark.parametrize("strategy",
                         ["no-basins", "with-basins", "only-basins"])
def test_export_datasets_basin_based(qtbot, strategy):
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # add 1 dataslots
    path = data_path / "cytoshot_blood.rtdc"
    slot_ids = mw.add_dataslot(paths=[path])

    # add a filter and activate it
    filt_id = mw.add_filter()
    filt = mw.pipeline.get_filter(filt_id)
    filt.limit_events = [True, 3]
    mw.pipeline.set_element_active(slot_ids[0], filt_id)

    # perform the export
    tmpd = tempfile.mkdtemp(prefix="shapeout2_test_data_export_")
    mw.settings.setValue("paths/export data", tmpd)

    # create export dialog manually (asks user for directory)
    dlg = export.ExportData(mw, pipeline=mw.pipeline)
    data_index = dlg.comboBox_storage.findData(strategy)
    assert data_index >= 0, "sanity check"
    dlg.comboBox_storage.setCurrentIndex(data_index)

    # Everything is set up already (.rtdc export, innate features selected).
    # Click OK.
    buttons = dlg.buttonBox.buttons()
    qtbot.mouseClick(buttons[0], QtCore.Qt.MouseButton.LeftButton)

    # make sure we have one .rtdc file
    exported = list(pathlib.Path(tmpd).glob("*.rtdc"))
    assert len(exported) == 1

    # make sure that file has three events and contains the logs and tables
    with dclab.new_dataset(exported[0]) as ds:
        assert len(ds) == 3
        assert np.allclose(ds["deform"][1],
                           0.20763598175592435,
                           atol=1e-7,
                           rtol=0
                           )
        if strategy == "no-basins":
            assert not ds.basins
            assert len(ds.h5file["events"]) > 5
        elif strategy == "with-basins":
            assert len(ds.basins) == 1
            assert len(ds.h5file["events"]) > 5
        elif strategy == "only-basins":
            assert len(ds.basins) == 1
            assert sorted(ds.h5file["events"]) == ["basinmap0"]
