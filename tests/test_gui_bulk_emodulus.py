"""Test bulk action for emodulus computation"""
import pathlib
import tempfile

import dclab
import h5py
import numpy as np
import pytest
from PyQt6 import QtWidgets

from dcscope.gui import bulk
from dcscope import session

# for fixtures
import conftest  # noqa: F401


datapath = pathlib.Path(__file__).parent / "data"


def make_dataset(medium="CellCarrier", temp=22.5, temp_range=[22, 23],
                 chip_region="channel"):
    # create a fake dataset
    path = datapath / "calibration_beads_47.rtdc"
    ds = dclab.new_dataset(path)
    tmp = tempfile.mktemp(".rtdc", prefix="example_")
    ds.export.hdf5(tmp, features=["deform", "area_um", "bright_avg"])
    with h5py.File(tmp, mode="a") as h5:
        h5["events/temp"] = np.linspace(temp_range[0], temp_range[1], len(ds))
        if medium is None:
            h5.attrs.pop("setup:medium")
        else:
            h5.attrs["setup:medium"] = medium
        h5.attrs["setup:temperature"] = temp
        h5.attrs["setup:chip region"] = chip_region
    return pathlib.Path(tmp)


@pytest.fixture(autouse=True)
def run_around_tests():
    # Code that will run before your test, for example:
    session.clear_session()
    # A test function will be run at this point
    yield
    # Code that will run after your test, for example:
    session.clear_session()


@pytest.fixture(autouse=True)
def warnings_shown(monkeypatch):
    """Record message box warnings instead of showing them"""
    shown = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning",
                        lambda parent, title, text, *args, **kwargs:
                        shown.append((title, text)))
    return shown


def test_manual_basic(qtbot, mw):
    """Most simple test"""
    qtbot.addWidget(mw)

    # add a dataslot
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])
    mw.add_dataslot(paths=[path])

    # sanity check (no emodulus should be available)
    for slot in mw.pipeline.slots:
        ds = slot.get_dataset()
        assert "emodulus" not in ds
        assert ds.config["setup"]["medium"] == "CellCarrierB"

    # create bulk action dialog manually
    dlg = bulk.BulkActionEmodulus(mw, pipeline=mw.pipeline)

    # sanity check: default viscosity model should be "buyukurganci-2022"
    ivdm = dlg.ui.comboBox_visc_model.findData("buyukurganci-2022")
    assert dlg.ui.comboBox_visc_model.currentIndex() == ivdm
    assert dlg.ui.comboBox_visc_model.currentText() == "Buyukurganci (2022)"
    imed = dlg.ui.comboBox_medium.findData("0.59% MC-PBS")
    assert dlg.ui.comboBox_medium.itemText(imed) == \
        "0.59% MC-PBS (CellCarrierB)"

    dlg.ui.comboBox_temp.setCurrentIndex(
        dlg.ui.comboBox_temp.findData("manual"))
    dlg.ui.doubleSpinBox_temp.setValue(29.5)
    dlg.on_ok()

    for slot in mw.pipeline.slots:
        ds = slot.get_dataset()
        assert "emodulus" in ds
        assert ds.config["setup"]["medium"] == "CellCarrierB"
        assert ds.config["calculation"]["emodulus lut"] == "LE-2D-FEM-19"
        assert ds.config["calculation"]["emodulus medium"] == "CellCarrierB"
        assert ds.config["calculation"]["emodulus temperature"] == 29.5
        assert ds.config["calculation"]["emodulus viscosity model"] == \
            "buyukurganci-2022"
        assert "emodulus viscosity" not in ds.config["calculation"]


def test_manual_wrong_medium(qtbot, mw, warnings_shown):
    """Deliberately set wrong medium"""
    qtbot.addWidget(mw)

    # add a dataslot
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])
    mw.add_dataslot(paths=[path])

    # create bulk action dialog manually
    dlg = bulk.BulkActionEmodulus(mw, pipeline=mw.pipeline)
    dlg.ui.comboBox_temp.setCurrentIndex(
        dlg.ui.comboBox_temp.findData("manual"))
    dlg.ui.doubleSpinBox_temp.setValue(29.5)
    # Set medium to "water". This should not change the emodulus medium.
    dlg.ui.comboBox_medium.setCurrentIndex(
        dlg.ui.comboBox_medium.findData("water"))

    dlg.on_ok()

    # The user is informed that the medium was not changed (#124)
    assert len(warnings_shown) == 1
    assert warnings_shown[0][1].count(": 0.59% MC-PBS (CellCarrierB)") == 2

    for slot in mw.pipeline.slots:
        ds = slot.get_dataset()
        assert "emodulus" in ds
        assert ds.config["setup"]["medium"] == "CellCarrierB"
        assert ds.config["calculation"]["emodulus lut"] == "LE-2D-FEM-19"
        assert ds.config["calculation"]["emodulus medium"] == "CellCarrierB"
        assert ds.config["calculation"]["emodulus temperature"] == 29.5
        assert ds.config["calculation"]["emodulus viscosity model"] == \
            "buyukurganci-2022"
        assert "emodulus viscosity" not in ds.config["calculation"]


def test_temperature_feature(qtbot, mw):
    qtbot.addWidget(mw)

    # add custom dataslot
    path = make_dataset(medium="CellCarrier", temp=22.5, temp_range=[22, 23])
    mw.add_dataslot(paths=[path])
    mw.add_dataslot(paths=[path])

    # create bulk action dialog manually
    dlg = bulk.BulkActionEmodulus(mw, pipeline=mw.pipeline)
    dlg.ui.comboBox_temp.setCurrentIndex(
        dlg.ui.comboBox_temp.findData("feature"))
    dlg.on_ok()

    for slot in mw.pipeline.slots:
        ds = slot.get_dataset()
        assert "emodulus" in ds
        assert ds.config["setup"]["medium"] == "CellCarrier"
        assert ds.config["calculation"]["emodulus lut"] == "LE-2D-FEM-19"
        assert ds.config["calculation"]["emodulus medium"] == "CellCarrier"
        assert "emodulus temperature" not in ds.config["calculation"]
        assert "emodulus viscosity" not in ds.config["calculation"]
        assert ds.config["calculation"]["emodulus viscosity model"] == \
            "buyukurganci-2022"


def test_viscosity(qtbot, mw):
    qtbot.addWidget(mw)

    # add custom dataslot
    path = make_dataset(medium="other")
    mw.add_dataslot(paths=[path])
    mw.add_dataslot(paths=[path])

    # create bulk action dialog manually
    dlg = bulk.BulkActionEmodulus(mw, pipeline=mw.pipeline)
    dlg.ui.comboBox_medium.setCurrentIndex(
        dlg.ui.comboBox_medium.findData("other"))
    dlg.ui.doubleSpinBox_visc.setValue(1.0)
    dlg.on_ok()

    for slot in mw.pipeline.slots:
        ds = slot.get_dataset()
        assert "emodulus" in ds
        assert ds.config["setup"]["medium"] == "other"
        assert ds.config["calculation"]["emodulus lut"] == "LE-2D-FEM-19"
        assert "emodulus medium" not in ds.config["calculation"]
        assert "emodulus temperature" not in ds.config["calculation"]
        assert ds.config["calculation"]["emodulus viscosity"] == 1.0
        assert "emodulus viscosity model" not in ds.config["calculation"]


def test_viscosity_compute(qtbot, mw):
    qtbot.addWidget(mw)

    # add custom dataslot
    path = make_dataset(medium="other")
    mw.add_dataslot(paths=[path])
    mw.add_dataslot(paths=[path])

    # create bulk action dialog manually
    dlg = bulk.BulkActionEmodulus(mw, pipeline=mw.pipeline)
    dlg.ui.comboBox_medium.setCurrentIndex(
        dlg.ui.comboBox_medium.findData("0.59% MC-PBS"))
    dlg.ui.comboBox_temp.setCurrentIndex(
        dlg.ui.comboBox_temp.findData("manual"))
    assert dlg.ui.doubleSpinBox_temp.value() == 23
    assert dlg.ui.doubleSpinBox_visc.value() == 3.57

    dlg.ui.doubleSpinBox_temp.setValue(24.5)
    assert dlg.ui.doubleSpinBox_temp.value() == 24.5
    assert dlg.ui.doubleSpinBox_visc.value() == 3.51
    dlg.on_ok()

    for slot in mw.pipeline.slots:
        ds = slot.get_dataset()
        assert "emodulus" in ds
        assert ds.config["setup"]["medium"] == "other"
        assert ds.config["calculation"]["emodulus lut"] == "LE-2D-FEM-19"
        assert ds.config["calculation"]["emodulus medium"] == "0.59% MC-PBS"
        assert ds.config["calculation"]["emodulus temperature"] == 24.5
        assert ds.config["calculation"]["emodulus viscosity model"] \
            == "buyukurganci-2022"


def test_wrong_medium_viscosity(qtbot, mw, warnings_shown):
    """Deliberately set wrong visosity"""
    qtbot.addWidget(mw)

    # add a dataslot
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])
    mw.add_dataslot(paths=[path])

    # create bulk action dialog manually
    dlg = bulk.BulkActionEmodulus(mw, pipeline=mw.pipeline)
    dlg.ui.comboBox_medium.setCurrentIndex(
        dlg.ui.comboBox_medium.findData("other"))
    dlg.ui.doubleSpinBox_visc.setValue(1.0)  # random number

    dlg.on_ok()
    assert len(warnings_shown) == 1

    for slot in mw.pipeline.slots:
        ds = slot.get_dataset()
        assert "emodulus" not in ds, "because medium is fixed"
        assert ds.config["setup"]["medium"] == "CellCarrierB"
        assert ds.config["calculation"]["emodulus lut"] == "LE-2D-FEM-19"
        assert ds.config["calculation"]["emodulus medium"] == "CellCarrierB"
        assert "emodulus temperature" not in ds.config["calculation"]
        assert "emodulus viscosity" not in ds.config["calculation"]
        assert ds.config["calculation"]["emodulus viscosity model"] == \
            "buyukurganci-2022"


def test_lut_selection(qtbot, mw):
    qtbot.addWidget(mw)

    # add a dataslot
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])
    mw.add_dataslot(paths=[path])

    # create bulk action dialog manually
    dlg = bulk.BulkActionEmodulus(mw, pipeline=mw.pipeline)
    dlg.ui.comboBox_medium.setCurrentIndex(
        dlg.ui.comboBox_medium.findData("other"))
    dlg.ui.doubleSpinBox_visc.setValue(1.0)  # random number
    dlg.ui.comboBox_lut.setCurrentIndex(
        dlg.ui.comboBox_lut.findData("HE-2D-FEM-22"))

    dlg.on_ok()

    for slot in mw.pipeline.slots:
        ds = slot.get_dataset()
        assert "emodulus" not in ds, "because medium is fixed"
        assert ds.config["setup"]["medium"] == "CellCarrierB"
        assert ds.config["calculation"]["emodulus lut"] == "HE-2D-FEM-22"
        assert ds.config["calculation"]["emodulus medium"] == "CellCarrierB"
        assert "emodulus temperature" not in ds.config["calculation"]
        assert "emodulus viscosity" not in ds.config["calculation"]
        assert ds.config["calculation"]["emodulus viscosity model"] == \
            "buyukurganci-2022"


def test_wrong_medium_warning_only_for_fixed_media_issue_124(
        qtbot, mw, warnings_shown):
    """Only list datasets for which the medium could not be changed"""
    qtbot.addWidget(mw)
    path_known = make_dataset(medium="CellCarrier")
    path_other = make_dataset(medium="other")
    mw.add_dataslot(paths=[path_known, path_other])

    dlg = bulk.BulkActionEmodulus(mw, pipeline=mw.pipeline)
    dlg.ui.comboBox_medium.setCurrentIndex(
        dlg.ui.comboBox_medium.findData("other"))
    dlg.ui.doubleSpinBox_visc.setValue(6.74)
    dlg.on_ok()

    slot_known, slot_other = mw.pipeline.slots
    assert slot_known.__getstate__()["emodulus"]["emodulus medium"] \
        == "CellCarrier"
    assert slot_other.__getstate__()["emodulus"]["emodulus medium"] \
        == "other"
    assert slot_other.__getstate__()["emodulus"]["emodulus viscosity"] \
        == 6.74

    assert len(warnings_shown) == 1
    text = warnings_shown[0][1]
    # only one dataset is listed
    assert text.count("\n- ") == 1
    assert text.count(f"- {slot_known.name}: 0.49% MC-PBS (CellCarrier)") == 1


def test_no_warning_for_unchanged_medium(qtbot, mw, warnings_shown):
    qtbot.addWidget(mw)
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])
    dlg = bulk.BulkActionEmodulus(mw, pipeline=mw.pipeline)
    assert dlg.ui.comboBox_medium.currentData() == "unchanged"
    dlg.on_ok()
    assert not warnings_shown
