"""Tests for the background computations of the pipeline plots"""
import copy

import dclab
import numpy as np
import pytest

from dcscope.gui.pipeline_plot_compute import get_emodulus_warnings
from dcscope.pipeline.plot import DEFAULT_STATE


def make_dataset(num_outside_lut=0, temperature=25.0):
    """Dataset with Young's modulus (some events outside of the LUT)"""
    rng = np.random.default_rng(42)
    area = np.concatenate([rng.uniform(50, 80, 100),
                           np.full(num_outside_lut, 10.0)])
    deform = np.concatenate([rng.uniform(0.02, 0.05, 100),
                             np.full(num_outside_lut, 0.2)])
    ds = dclab.new_dataset({"area_um": area, "deform": deform})
    ds.config["setup"]["channel width"] = 20
    ds.config["setup"]["flow rate"] = 0.04
    ds.config["imaging"]["pixel size"] = 0.34
    ds.config["calculation"] = {
        "emodulus lut": "LE-2D-FEM-19",
        "emodulus medium": "CellCarrier",
        "emodulus temperature": temperature,
        "emodulus viscosity model": "buyukurganci-2022",
    }
    return ds


def plot_state(axis_y="emodulus"):
    state = copy.deepcopy(DEFAULT_STATE)
    state["general"]["axis y"] = axis_y
    return state


@pytest.mark.filterwarnings(
    "ignore::dclab.features.emodulus.YoungsModulusLookupTableExceededWarning")
def test_emodulus_warnings_lut_exceeded_issue_144():
    ds = make_dataset(num_outside_lut=50)
    warnings = get_emodulus_warnings(ds, plot_state())
    assert len(warnings) == 1
    assert warnings[0][0] == "33% of events outside LUT"
    assert warnings[0][1].count("LE-2D-FEM-19")
    # no warnings if the Young's modulus is not plotted
    assert get_emodulus_warnings(ds, plot_state("deform")) == []
    # unless it is used for the marker hue
    state = plot_state("deform")
    state["scatter"]["marker hue"] = "feature"
    state["scatter"]["hue feature"] = "emodulus"
    assert len(get_emodulus_warnings(ds, state)) == 1


@pytest.mark.filterwarnings(
    "ignore::dclab.features.emodulus.viscosity.TemperatureOutOfRangeWarning")
def test_emodulus_warnings_temperature_out_of_range_issue_144():
    # valid range of "buyukurganci-2022" is 22 to 37 degC
    ds = make_dataset(temperature=40)
    warnings = get_emodulus_warnings(ds, plot_state())
    assert len(warnings) == 1
    assert warnings[0][0] == "Temperature out of range"
    # the description contains the valid range
    assert warnings[0][1].count("[22, 37]")


def test_emodulus_warnings_none():
    ds = make_dataset()
    assert get_emodulus_warnings(ds, plot_state()) == []
    # filtered events only
    ds2 = make_dataset(num_outside_lut=50)
    ds2.config["filtering"]["deform min"] = 0
    ds2.config["filtering"]["deform max"] = 0.1
    ds2.apply_filter()
    assert get_emodulus_warnings(ds2, plot_state()) == []
