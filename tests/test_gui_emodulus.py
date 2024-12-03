"""Test computation of emodulus"""
import pathlib
import tempfile

from PyQt6 import QtCore, QtWidgets

import dclab
import h5py
import numpy as np
from shapeout2.gui.main import ShapeOut2
from shapeout2 import session
import pytest

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


def test_allow_to_set_manual_temperature_for_known_medium(qtbot):
    """Fixes regression introduced in 2.4.0"""
    mw = ShapeOut2()
    qtbot.addWidget(mw)
    # add fake measurement
    path1 = make_dataset(medium=None, temp=23.5)
    mw.add_dataslot(paths=[path1])
    wsl = mw.widget_ana_view.widget_slot

    # 1. test whether we can actually select things in comboBox_temp
    ccidx = wsl.comboBox_medium.findData("CellCarrier")
    wsl.comboBox_medium.setCurrentIndex(ccidx)
    assert wsl.comboBox_temp.isEnabled()

    # 2. test whether we can select manual
    manidx = wsl.comboBox_temp.findData("manual")
    wsl.comboBox_temp.setCurrentIndex(manidx)
    assert wsl.doubleSpinBox_temp.isEnabled()
    assert not wsl.doubleSpinBox_temp.isReadOnly()

    # 3. test whether we can select config and the the temperature
    # should be 23.5
    conidx = wsl.comboBox_temp.findData("config")
    wsl.comboBox_temp.setCurrentIndex(conidx)
    assert wsl.doubleSpinBox_temp.isEnabled()
    assert wsl.doubleSpinBox_temp.isReadOnly()
    assert wsl.doubleSpinBox_temp.value() == 23.5


def test_empty_medium_string_should_offer_user_edit(qtbot):
    mw = ShapeOut2()
    qtbot.addWidget(mw)
    # add fake measurement
    path1 = make_dataset(medium=" ")
    mw.add_dataslot(paths=[path1])
    wsl = mw.widget_ana_view.widget_slot
    ds = mw.pipeline.slots[0].get_dataset()
    assert ds.config["setup"]["medium"] == " "
    assert wsl.comboBox_medium.currentData() == "other"
    assert not wsl.doubleSpinBox_visc.isReadOnly(), "Should be editable"
    assert wsl.doubleSpinBox_visc.isEnabled(), "Should be editable"
    assert np.isnan(wsl.__getstate__()["emodulus"]["emodulus temperature"])
    assert wsl.__getstate__()["emodulus"]["emodulus medium"] == "other"
    assert wsl.__getstate__()["emodulus"]["emodulus scenario"] is None


def test_other_medium_viscosity_editable_issue_49(qtbot):
    mw = ShapeOut2()
    qtbot.addWidget(mw)
    # add fake measurement
    path1 = make_dataset(medium=None)
    mw.add_dataslot(paths=[path1])
    wsl = mw.widget_ana_view.widget_slot
    ds = mw.pipeline.slots[0].get_dataset()
    assert "medium" not in ds.config["setup"], "sanity check (medium removed)"
    oidx = wsl.comboBox_medium.findData("other")
    wsl.comboBox_medium.setCurrentIndex(oidx)
    assert not wsl.doubleSpinBox_visc.isReadOnly(), "Should be editable"
    assert wsl.doubleSpinBox_visc.isEnabled(), "Should be editable"


@pytest.mark.filterwarnings(
    'ignore::dclab.features.emodulus.YoungsModulusLookupTableExceededWarning')
def test_simple(qtbot):
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # add fake measurement
    path = make_dataset(medium="CellCarrier", temp=22.5, temp_range=[22, 23])

    with dclab.new_dataset(path) as ds:
        # Youngs modulus can readily be computed
        # https://dclab.readthedocs.io/en/latest/sec_av_emodulus.html
        ds.config["calculation"]["emodulus medium"] = \
            ds.config["setup"]["medium"]
        ds.config["calculation"]["emodulus lut"] = "LE-2D-FEM-19"
        ds.config["calculation"]["emodulus viscosity model"] = "herold-2017"
        emodA = np.array(ds["emodulus"], copy=True)
        ds.config["calculation"]["emodulus temperature"] = \
            ds.config["setup"]["temperature"]
        emodC = np.array(ds["emodulus"], copy=True)
        assert not np.allclose(emodA, emodC, atol=0, rtol=1e-12,
                               equal_nan=True), "sanity check"

    mw.add_dataslot(paths=[path])
    wsl = mw.widget_ana_view.widget_slot
    idvm = wsl.comboBox_visc_model.findData("herold-2017")
    assert idvm >= 0
    wsl.comboBox_visc_model.setCurrentIndex(idvm)
    wsl.write_slot()

    # default values
    assert wsl.comboBox_medium.currentData() == "CellCarrier"
    assert wsl.comboBox_temp.currentData() == "feature"
    assert wsl.comboBox_visc_model.currentData() == "herold-2017"

    # scenario A (this is already set by default)
    ds1 = mw.pipeline.slots[0].get_dataset()
    assert np.allclose(ds1["emodulus"], emodA, atol=0, rtol=1e-12,
                       equal_nan=True)

    # scenario C (switch to config)
    wsl.comboBox_temp.setCurrentIndex(wsl.comboBox_temp.findData("config"))
    qtbot.mouseClick(wsl.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)
    ds2 = mw.pipeline.slots[0].get_dataset()
    assert np.allclose(ds2["emodulus"], emodC, atol=0, rtol=1e-12,
                       equal_nan=True)

    # scenario C (switch to manual)
    wsl.comboBox_temp.setCurrentIndex(wsl.comboBox_temp.findData("manual"))
    wsl.doubleSpinBox_temp.setValue(22.5)
    qtbot.mouseClick(wsl.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)
    ds3 = mw.pipeline.slots[0].get_dataset()
    assert np.allclose(ds3["emodulus"], emodC, atol=0, rtol=1e-12,
                       equal_nan=True)

    try:
        path.unlink()
    except BaseException:
        pass


def test_switch_and_update_chip_region(qtbot):
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # add fake measurement
    path1 = make_dataset(medium="CellCarrier", temp=22.5, temp_range=[22, 23],
                         chip_region="channel")
    path2 = make_dataset(medium="CellCarrier", temp=22.5, temp_range=[22, 23],
                         chip_region="reservoir")

    slot_id1, slot_id2 = mw.add_dataslot(paths=[path1, path2])
    wsl = mw.widget_ana_view.widget_slot

    # select the first slot
    em1 = mw.block_matrix.get_widget(slot_id=slot_id1)
    em2 = mw.block_matrix.get_widget(slot_id=slot_id2)
    qtbot.mouseClick(em1.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)
    # set temperature manually
    idm = wsl.comboBox_temp.findData("manual")
    wsl.comboBox_temp.setCurrentIndex(idm)
    assert wsl.comboBox_temp.currentData() == "manual"
    wsl.doubleSpinBox_temp.setValue(20.0)
    assert wsl.doubleSpinBox_temp.value() == 20
    qtbot.mouseClick(wsl.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)
    QtWidgets.QApplication.processEvents(
        QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
    # check whether that worked
    assert wsl.get_dataset(
    ).config["calculation"]["emodulus temperature"] == 20

    # switch to the second (reservoir) measurement
    qtbot.mouseClick(em2.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)
    assert not wsl.groupBox_emod.isVisible()
    # now switch back
    qtbot.mouseClick(em1.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)

    # This is the actual test
    assert wsl.doubleSpinBox_temp.value() == 20

    try:
        path1.unlink()
        path2.unlink()
    except BaseException:
        pass


def test_switch_and_update_medium(qtbot):
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # add fake measurement
    path1 = make_dataset(medium="CellCarrier", temp=22.5, temp_range=[22, 23])
    path2 = make_dataset(medium="UserDefined", temp=22.5, temp_range=[22, 23])

    slot_id1, slot_id2 = mw.add_dataslot(paths=[path1, path2])
    wsl = mw.widget_ana_view.widget_slot

    # select the first slot
    em1 = mw.block_matrix.get_widget(slot_id=slot_id1)
    em2 = mw.block_matrix.get_widget(slot_id=slot_id2)
    qtbot.mouseClick(em1.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)
    # set temperature manually
    idm = wsl.comboBox_temp.findData("manual")
    wsl.comboBox_temp.setCurrentIndex(idm)
    assert wsl.comboBox_temp.currentData() == "manual"
    wsl.doubleSpinBox_temp.setValue(20.0)
    assert wsl.doubleSpinBox_temp.value() == 20
    qtbot.mouseClick(wsl.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)
    QtWidgets.QApplication.processEvents(
        QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
    # check whether that worked
    assert wsl.get_dataset(
    ).config["calculation"]["emodulus temperature"] == 20

    # switch to the second (user-defined medium) measurement
    qtbot.mouseClick(em2.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)
    assert wsl.comboBox_medium.currentData() == "UserDefined"
    assert not wsl.doubleSpinBox_visc.isReadOnly(), "Should be editable"
    assert wsl.doubleSpinBox_visc.isEnabled(), "Should be editable"
    assert not wsl.doubleSpinBox_temp.isEnabled(), "Should not be editable"
    # now switch back
    qtbot.mouseClick(em1.toolButton_modify, QtCore.Qt.MouseButton.LeftButton)

    # This is the actual test
    assert wsl.doubleSpinBox_temp.value() == 20
    assert wsl.doubleSpinBox_temp.isEnabled(), "Should be editable"

    try:
        path1.unlink()
        path2.unlink()
    except BaseException:
        pass


def test_user_defined_medium_should_work(qtbot):
    mw = ShapeOut2()
    qtbot.addWidget(mw)
    # add fake measurement
    path1 = make_dataset(medium="MyMedium")
    mw.add_dataslot(paths=[path1])
    wsl = mw.widget_ana_view.widget_slot
    ds = mw.pipeline.slots[0].get_dataset()
    assert ds.config["setup"]["medium"] == "MyMedium", "sanity check"
    assert wsl.comboBox_medium.currentData() == "MyMedium"
    assert not wsl.doubleSpinBox_visc.isReadOnly(), "Should be editable"
    assert wsl.doubleSpinBox_visc.isEnabled(), "Should be editable"
    wsl.doubleSpinBox_visc.setValue(12.1)
    assert wsl.__getstate__()["emodulus"]["emodulus viscosity"] == 12.1
    assert np.isnan(wsl.__getstate__()["emodulus"]["emodulus temperature"])
    assert wsl.__getstate__()["emodulus"]["emodulus medium"] == "MyMedium"
    assert wsl.__getstate__()["emodulus"]["emodulus scenario"] is None


def test_changeable_lut_selection(qtbot):
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # add fake measurement
    path1 = make_dataset(medium="CellCarrier", temp=22.5, temp_range=[22, 23])

    mw.add_dataslot(paths=[path1])
    wsl = mw.widget_ana_view.widget_slot
    ds = mw.pipeline.slots[0].get_dataset()

    assert ds.config["setup"]["medium"] == "CellCarrier", "sanity check"
    assert wsl.comboBox_medium.currentData() == "CellCarrier"

    # set viscosity model manually
    idvm = wsl.comboBox_visc_model.findData("buyukurganci-2022")
    wsl.comboBox_visc_model.setCurrentIndex(idvm)
    # set lut manually
    idlut = wsl.comboBox_lut.findData("HE-2D-FEM-22")
    wsl.comboBox_lut.setCurrentIndex(idlut)
    qtbot.mouseClick(wsl.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)
    QtWidgets.QApplication.processEvents(
        QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)

    # check LUT selection
    assert wsl.comboBox_lut.currentData() == "HE-2D-FEM-22"

    # check whether that worked
    assert wsl.get_dataset(
    ).config["calculation"]["emodulus lut"] == "HE-2D-FEM-22"
    assert wsl.get_dataset(
    ).config["calculation"]["emodulus viscosity model"] == "buyukurganci-2022"

    # set different lut manually
    idlut = wsl.comboBox_lut.findData("HE-3D-FEM-22")
    wsl.comboBox_lut.setCurrentIndex(idlut)
    qtbot.mouseClick(wsl.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)
    QtWidgets.QApplication.processEvents(
        QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)

    # check new LUT selection
    assert wsl.comboBox_lut.currentData() == "HE-3D-FEM-22"
    # check whether that worked
    assert wsl.get_dataset(
    ).config["calculation"]["emodulus lut"] == "HE-3D-FEM-22"

    # This is the actual test
    assert wsl.comboBox_visc_model.currentData() == "buyukurganci-2022"
    assert wsl.comboBox_lut.currentText() == "HE-3D-FEM-22"

    try:
        path1.unlink()
    except BaseException:
        pass


def test_viscosity_defaults_to_buyukurganci_2022(qtbot):
    mw = ShapeOut2()
    qtbot.addWidget(mw)

    # add fake measurement
    path1 = make_dataset(medium="CellCarrier", temp=22.5, temp_range=[22, 23])

    mw.add_dataslot(paths=[path1])
    wsl = mw.widget_ana_view.widget_slot
    ds = mw.pipeline.slots[0].get_dataset()

    assert ds.config["setup"]["medium"] == "CellCarrier", "sanity check"
    assert wsl.comboBox_medium.currentData() == "CellCarrier"

    # the buyukurganci-2022 viscosity model should be the default
    idvm_loc = wsl.comboBox_visc_model.findData("buyukurganci-2022")
    idvm_actual = wsl.comboBox_visc_model.currentIndex()
    assert idvm_loc == idvm_actual
