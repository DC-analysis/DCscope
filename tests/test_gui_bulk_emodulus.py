"""Test bulk action for emodulus computation"""
import pathlib
import tempfile

import dclab
import h5py
import numpy as np
import pytest

from dcscope.gui.main import DCscope
from dcscope.gui import bulk
from dcscope import session

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


def test_manual_basic(qtbot):
    """Most simple test"""
    mw = DCscope()
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
    ivdm = dlg.comboBox_visc_model.findData("buyukurganci-2022")
    assert dlg.comboBox_visc_model.currentIndex() == ivdm

    dlg.comboBox_temp.setCurrentIndex(dlg.comboBox_temp.findData("manual"))
    dlg.doubleSpinBox_temp.setValue(29.5)
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


def test_manual_wrong_medium(qtbot):
    """Deliberately set wrong medium"""
    mw = DCscope()
    qtbot.addWidget(mw)

    # add a dataslot
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])
    mw.add_dataslot(paths=[path])

    # create bulk action dialog manually
    dlg = bulk.BulkActionEmodulus(mw, pipeline=mw.pipeline)
    dlg.comboBox_temp.setCurrentIndex(dlg.comboBox_temp.findData("manual"))
    dlg.doubleSpinBox_temp.setValue(29.5)
    # Set medium to "water". This should not change the emodulus medium.
    dlg.comboBox_medium.setCurrentIndex(dlg.comboBox_medium.findData("water"))

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


def test_temperature_feature(qtbot):
    mw = DCscope()
    qtbot.addWidget(mw)

    # add custom dataslot
    path = make_dataset(medium="CellCarrier", temp=22.5, temp_range=[22, 23])
    mw.add_dataslot(paths=[path])
    mw.add_dataslot(paths=[path])

    # create bulk action dialog manually
    dlg = bulk.BulkActionEmodulus(mw, pipeline=mw.pipeline)
    dlg.comboBox_temp.setCurrentIndex(dlg.comboBox_temp.findData("feature"))
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


def test_viscosity(qtbot):
    mw = DCscope()
    qtbot.addWidget(mw)

    # add custom dataslot
    path = make_dataset(medium="other")
    mw.add_dataslot(paths=[path])
    mw.add_dataslot(paths=[path])

    # create bulk action dialog manually
    dlg = bulk.BulkActionEmodulus(mw, pipeline=mw.pipeline)
    dlg.comboBox_medium.setCurrentIndex(dlg.comboBox_medium.findData("other"))
    dlg.doubleSpinBox_visc.setValue(1.0)
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


def test_viscosity_compute(qtbot):
    mw = DCscope()
    qtbot.addWidget(mw)

    # add custom dataslot
    path = make_dataset(medium="other")
    mw.add_dataslot(paths=[path])
    mw.add_dataslot(paths=[path])

    # create bulk action dialog manually
    dlg = bulk.BulkActionEmodulus(mw, pipeline=mw.pipeline)
    dlg.comboBox_medium.setCurrentIndex(
        dlg.comboBox_medium.findData("0.59% MC-PBS"))
    dlg.comboBox_temp.setCurrentIndex(dlg.comboBox_temp.findData("manual"))
    assert dlg.doubleSpinBox_temp.value() == 23
    assert dlg.doubleSpinBox_visc.value() == 3.57

    dlg.doubleSpinBox_temp.setValue(24.5)
    assert dlg.doubleSpinBox_temp.value() == 24.5
    assert dlg.doubleSpinBox_visc.value() == 3.51
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


def test_wrong_medium_viscosity(qtbot):
    """Deliberately set wrong visosity"""
    mw = DCscope()
    qtbot.addWidget(mw)

    # add a dataslot
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])
    mw.add_dataslot(paths=[path])

    # create bulk action dialog manually
    dlg = bulk.BulkActionEmodulus(mw, pipeline=mw.pipeline)
    dlg.comboBox_medium.setCurrentIndex(dlg.comboBox_medium.findData("other"))
    dlg.doubleSpinBox_visc.setValue(1.0)  # random number

    dlg.on_ok()

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


def test_lut_selection(qtbot):
    mw = DCscope()
    qtbot.addWidget(mw)

    # add a dataslot
    path = datapath / "calibration_beads_47.rtdc"
    mw.add_dataslot(paths=[path])
    mw.add_dataslot(paths=[path])

    # create bulk action dialog manually
    dlg = bulk.BulkActionEmodulus(mw, pipeline=mw.pipeline)
    dlg.comboBox_medium.setCurrentIndex(dlg.comboBox_medium.findData("other"))
    dlg.doubleSpinBox_visc.setValue(1.0)  # random number
    dlg.comboBox_lut.setCurrentIndex(dlg.comboBox_lut.findData("HE-2D-FEM-22"))

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
