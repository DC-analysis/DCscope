"""User-defined default settings for new plots and datasets (#129)"""
import copy
import json
import logging

import dclab
from PyQt6 import QtCore

from ..pipeline.plot import DEFAULT_STATE as PLOT_DEFAULT_STATE

logger = logging.getLogger(__name__)

#: QSettings key for the user-defined default plot state (JSON string)
KEY_PLOT_STATE = "defaults/plot state"

#: QSettings keys for the default Young's modulus settings of new datasets
KEY_EMODULUS_LUT = "defaults/emodulus lut"
KEY_EMODULUS_VISC_MODEL = "defaults/emodulus viscosity model"

#: built-in Young's modulus defaults (see `dcscope.pipeline.dataslot`)
DEFAULT_EMODULUS_LUT = "LE-2D-FEM-19"
DEFAULT_EMODULUS_VISC_MODEL = "buyukurganci-2022"

#: viscosity models available for the Young's modulus computation
EMODULUS_VISC_MODELS = {"Buyukurganci (2022)": "buyukurganci-2022",
                        "Herold (2017)": "herold-2017"}

#: plot state keys that depend on a specific plot or on the data
#: and are thus not stored as defaults
PLOT_STATE_EXCLUDED = {
    "layout": ["name"],
    "general": ["auto range", "auto spacing",
                "range x", "range y",
                "spacing x", "spacing y"],
}


def _filter_plot_state(state):
    """Return the parts of `state` that may be used as plot defaults

    Only keys defined in the built-in default plot state are
    returned (excluding :const:`PLOT_STATE_EXCLUDED`). Values must
    have the same type as the built-in defaults (int and float are
    interchangeable, lists must have the same length).
    """
    filtered = {}
    for topic, defaults in PLOT_DEFAULT_STATE.items():
        if not isinstance(defaults, dict) or topic not in state:
            continue
        for key, default in defaults.items():
            if key in PLOT_STATE_EXCLUDED.get(topic, []):
                continue
            if key not in state[topic]:
                continue
            value = state[topic][key]
            if isinstance(default, bool):
                valid = isinstance(value, bool)
            elif isinstance(default, (int, float)):
                valid = (isinstance(value, (int, float))
                         and not isinstance(value, bool))
            elif isinstance(default, list):
                valid = (isinstance(value, list)
                         and len(value) == len(default))
            else:
                valid = isinstance(value, type(default))
            if valid:
                filtered.setdefault(topic, {})[key] = copy.deepcopy(value)
    return filtered


def get_plot_defaults(settings: QtCore.QSettings) -> dict:
    """Return the user-defined plot defaults (empty dict if not set)"""
    value = settings.value(KEY_PLOT_STATE, "")
    if not value:
        return {}
    try:
        state = json.loads(value)
    except (TypeError, ValueError):
        logger.warning(f"Ignoring invalid plot defaults: {value}")
        return {}
    if not isinstance(state, dict):
        return {}
    return _filter_plot_state(state)


def has_plot_defaults(settings: QtCore.QSettings) -> bool:
    """Whether user-defined plot defaults are set"""
    return bool(get_plot_defaults(settings))


def reset_plot_defaults(settings: QtCore.QSettings):
    """Remove the user-defined plot defaults"""
    settings.remove(KEY_PLOT_STATE)


def save_plot_defaults(settings: QtCore.QSettings, plot_state: dict):
    """Use the settings of `plot_state` as defaults for new plots"""
    settings.setValue(KEY_PLOT_STATE,
                      json.dumps(_filter_plot_state(plot_state)))


def apply_plot_defaults(settings: QtCore.QSettings, plot):
    """Apply the user-defined plot defaults to a new plot

    Parameters
    ----------
    settings: QtCore.QSettings
        Settings in which the defaults are stored
    plot: dcscope.pipeline.Plot
        Plot instance that is modified in-place
    """
    defaults = get_plot_defaults(settings)
    if defaults:
        state = plot.__getstate__()
        for topic in defaults:
            state[topic].update(defaults[topic])
        plot.__setstate__(state)


def get_emodulus_lut_choices() -> list[str]:
    """Return the identifiers of the available look-up tables"""
    return list(
        dclab.features.emodulus.load.get_internal_lut_names_dict().keys())


def get_emodulus_defaults(settings: QtCore.QSettings) -> dict:
    """Return default LUT and viscosity model for new datasets

    Invalid values (e.g. a LUT that is not available anymore) are
    replaced by the built-in defaults.
    """
    lut = str(settings.value(KEY_EMODULUS_LUT, DEFAULT_EMODULUS_LUT))
    if lut not in get_emodulus_lut_choices():
        lut = DEFAULT_EMODULUS_LUT
    visc_model = str(settings.value(KEY_EMODULUS_VISC_MODEL,
                                    DEFAULT_EMODULUS_VISC_MODEL))
    if visc_model not in EMODULUS_VISC_MODELS.values():
        visc_model = DEFAULT_EMODULUS_VISC_MODEL
    return {
        "emodulus lut": lut,
        "emodulus viscosity model": visc_model,
    }


def apply_slot_defaults(settings: QtCore.QSettings, slot):
    """Apply the default Young's modulus settings to a new dataslot

    Parameters
    ----------
    settings: QtCore.QSettings
        Settings in which the defaults are stored
    slot: dcscope.pipeline.Dataslot
        Dataslot instance that is modified in-place
    """
    state = slot.__getstate__()
    state["emodulus"].update(get_emodulus_defaults(settings))
    slot.__setstate__(state)
