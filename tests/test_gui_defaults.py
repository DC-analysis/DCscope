"""Test user-defined default settings for new plots and datasets (#129)"""
import json
import pathlib

import pytest
from PyQt6 import QtCore, QtWidgets

from dcscope import session
from dcscope.gui import defaults, preferences
from dcscope.pipeline.plot import DEFAULT_STATE

import conftest  # noqa: F401


datapath = pathlib.Path(__file__).parent / "data"

DEFAULT_KEYS = [defaults.KEY_PLOT_STATE,
                defaults.KEY_EMODULUS_LUT,
                defaults.KEY_EMODULUS_VISC_MODEL]


@pytest.fixture(autouse=True)
def run_around_tests():
    session.clear_session()
    settings = QtCore.QSettings()
    for key in DEFAULT_KEYS:
        settings.remove(key)
    yield
    for key in DEFAULT_KEYS:
        settings.remove(key)
    session.clear_session()


def test_emodulus_defaults_for_new_dataslot(qtbot, mw, monkeypatch):
    qtbot.addWidget(mw)
    # "Please restart DCscope" message box after applying settings
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec",
                        lambda *args, **kwargs: None)

    # set the defaults via the preferences dialog
    dlg = preferences.Preferences(mw)
    qtbot.addWidget(dlg)
    for cb, data in [(dlg.ui.comboBox_defaults_lut, "HE-3D-FEM-22"),
                     (dlg.ui.comboBox_defaults_visc_model, "herold-2017")]:
        idx = cb.findData(data)
        assert idx >= 0
        cb.setCurrentIndex(idx)
    dlg.on_settings_apply()

    slot_id = mw.add_dataslot(
        paths=[datapath / "calibration_beads_47.rtdc"])[0]
    emod = mw.pipeline.get_slot(slot_id).__getstate__()["emodulus"]
    assert emod["emodulus lut"] == "HE-3D-FEM-22"
    assert emod["emodulus viscosity model"] == "herold-2017"


def test_emodulus_defaults_invalid_values():
    settings = QtCore.QSettings()
    settings.setValue(defaults.KEY_EMODULUS_LUT, "peter")
    settings.setValue(defaults.KEY_EMODULUS_VISC_MODEL, "hans")
    emod = defaults.get_emodulus_defaults(settings)
    assert emod["emodulus lut"] == defaults.DEFAULT_EMODULUS_LUT
    assert (emod["emodulus viscosity model"]
            == defaults.DEFAULT_EMODULUS_VISC_MODEL)


def test_emodulus_defaults_unchanged_without_settings(qtbot, mw):
    qtbot.addWidget(mw)
    slot_id = mw.add_dataslot(
        paths=[datapath / "calibration_beads_47.rtdc"])[0]
    emod = mw.pipeline.get_slot(slot_id).__getstate__()["emodulus"]
    assert emod["emodulus lut"] == "LE-2D-FEM-19"
    assert emod["emodulus viscosity model"] == "buyukurganci-2022"


def test_plot_defaults_invalid_settings():
    settings = QtCore.QSettings()
    # not JSON
    settings.setValue(defaults.KEY_PLOT_STATE, "{invalid")
    assert defaults.get_plot_defaults(settings) == {}
    # wrong types, unknown keys, and excluded keys are ignored
    settings.setValue(defaults.KEY_PLOT_STATE, json.dumps({
        "general": {"kde": "gauss",
                    "range x": [1, 2],
                    "unknown key": 1,
                    "isoelastics": "yes"},
        "contour": {"line widths": [1.0, 2.0, 3.0],
                    "percentiles": [90.0, 50.0]},
        "unknown topic": {"a": 1},
    }))
    assert defaults.get_plot_defaults(settings) == {
        "general": {"kde": "gauss"},
        "contour": {"percentiles": [90.0, 50.0]},
    }


def test_plot_defaults_save_apply_reset(qtbot, mw, monkeypatch):
    qtbot.addWidget(mw)
    monkeypatch.setattr(QtWidgets.QMessageBox, "information",
                        lambda *args, **kwargs: None)

    mw.add_dataslot(paths=[datapath / "calibration_beads_47.rtdc"])
    plot_id_1 = mw.add_plot()
    # sanity check
    state_1 = mw.pipeline.get_plot(plot_id_1).__getstate__()
    assert state_1["general"]["kde"] == "histogram"
    assert state_1["contour"]["line widths"] == [3.0, 1.5]

    # modify the plot settings in the Analysis View and save as default
    mw.widget_ana_view.ui.tabWidget.setCurrentWidget(
        mw.widget_ana_view.ui.tab_plot)
    pv = mw.widget_ana_view.ui.widget_plot
    pv.ui.comboBox_kde.setCurrentIndex(pv.ui.comboBox_kde.findData("gauss"))
    pv.ui.doubleSpinBox_lw_2.setValue(2.0)
    qtbot.mouseClick(pv.ui.pushButton_save_default,
                     QtCore.Qt.MouseButton.LeftButton)

    # the settings of the first plot are not changed (not applied)
    state_1 = mw.pipeline.get_plot(plot_id_1).__getstate__()
    assert state_1["general"]["kde"] == "histogram"

    # new plots use the defaults
    plot_id_2 = mw.add_plot()
    state_2 = mw.pipeline.get_plot(plot_id_2).__getstate__()
    assert state_2["general"]["kde"] == "gauss"
    assert state_2["contour"]["line widths"] == [3.0, 2.0]
    # but not the name or the identifier
    assert state_2["layout"]["name"] != state_1["layout"]["name"]
    assert state_2["identifier"] == plot_id_2

    # reset the defaults in the preferences
    dlg = preferences.Preferences(mw)
    qtbot.addWidget(dlg)
    assert dlg.ui.label_defaults_plot_status.text() == "user-defined"
    assert dlg.ui.pushButton_defaults_plot_reset.isEnabled()
    qtbot.mouseClick(dlg.ui.pushButton_defaults_plot_reset,
                     QtCore.Qt.MouseButton.LeftButton)
    assert dlg.ui.label_defaults_plot_status.text() == "built-in"
    assert not dlg.ui.pushButton_defaults_plot_reset.isEnabled()

    plot_id_3 = mw.add_plot()
    state_3 = mw.pipeline.get_plot(plot_id_3).__getstate__()
    assert state_3["general"]["kde"] == DEFAULT_STATE["general"]["kde"]
    assert (state_3["contour"]["line widths"]
            == DEFAULT_STATE["contour"]["line widths"])
