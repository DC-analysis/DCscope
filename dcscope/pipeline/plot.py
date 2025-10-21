import copy

import dclab
from dclab.kde import methods as kdem
import numpy as np

from ..util import hashobj


DEFAULT_STATE = {
    "identifier": "no default",
    "layout": {
        "column count": 2,
        "division": "multiscatter+contour",
        "label plots": True,
        "name": "no default",  # overridden by __init__
        "size x": 400,
        "size y": 400,
    },
    "general": {
        "auto range": True,  # this overrides range x and range y
        "axis x": "area_um",
        "axis y": "deform",
        "isoelastics": True,  # display isoelasticity lines
        "kde": "histogram",  # see dclab.kde.methods.methods
        "range x": [0, 0],  # equal means no preference
        "range y": [0, 0],
        "scale x": "linear",
        "scale y": "linear",
    },
    "scatter": {
        "colormap": "viridis",  # only applies when hue is "kde" or "feature"
        "downsample": True,
        "downsampling value": 5000,
        "enabled": True,
        "hue feature": "bright_avg",  # which feature to use, if set
        "hue max": 1,
        "hue min": 0,
        "marker alpha": 0.3,  # alpha value for feature-hue plots
        "marker hue": "kde",  # hue defined by: kde, dataset, feature, none
        "marker size": 3.0,  # marker size [pt]
        "show event count": True,  # display event count
    },
    "contour": {
        "enabled": True,
        "legend": False,  # display plot legend
        "zoomin": False,  # enable zoom-in functionality
        "line widths": [3.0, 1.5],  # contour line widths [pt]
        "line styles": ["solid", "dashed"],
        "percentiles": [95.0, 50.0],
        "spacing x": 2,  # spacing for "axis x" and linear "scale x"
        "spacing y": 0.005,  # spacing for "axis y" and linear "scale y"
    }
}

_kde_methods = sorted(kdem.methods.keys())
_kde_methods.remove("none")  # does not make sense here

STATE_OPTIONS = {
    "identifier": str,
    "layout": {
        "column count": int,
        "division": ["each", "merge", "multiscatter+contour", "onlycontours"],
        "label plots": bool,
        "name": str,
        "size x": float,
        "size y": float,
    },
    "general": {
        "auto range": bool,
        # This is not entirely correct, because `ml_score_???`
        # should also work.
        "axis x": dclab.dfn.scalar_feature_names,
        "axis y": dclab.dfn.scalar_feature_names,
        "isoelastics": bool,
        "kde": _kde_methods,
        "range x": (float,),
        "range y": (float,),
        "scale x": ["linear", "log"],
        "scale y": ["linear", "log"],
    },
    "scatter": {
        "colormap": ["bipolar", "grayblue", "graygreen", "grayorange",
                     "grayred", "inferno", "plasma", "viridis"],
        "downsampling": bool,
        "downsampling value": int,
        "enabled":  bool,
        # This is not entirely correct, because `ml_score_???`
        # should also work.
        "hue feature": dclab.dfn.scalar_feature_names,
        "hue max": float,
        "hue min": float,
        "marker alpha": float,
        "marker hue": ["dataset", "kde", "feature", "none"],
        "marker size": float,
        "show event count": bool,
    },
    "contour": {
        "enabled":  bool,
        "legend": bool,
        "zoomin": bool,
        "line widths": (float,),
        "line styles": (["solid", "dashed", "dotted"],),
        "percentiles": (float,),
        "spacing x": float,
        "spacing y": float,
    }
}


class Plot(object):
    """Handles plotting information in a pipeline"""
    _instance_counter = 0
    _instances = {}

    def __init__(self, identifier=None, name=None):
        Plot._instance_counter += 1
        if identifier is None:
            identifier = "Plot_{}".format(Plot._instance_counter)
            while identifier in Plot._instances:
                Plot._instance_counter += 1
                identifier = "Plot_{}".format(Plot._instance_counter)

        # initially, set default state
        self._state = copy.deepcopy(DEFAULT_STATE)

        if name is None:
            name = identifier
        #: unique identifier of the plot
        self.identifier = identifier
        #: user-defined name of the plot
        self.name = name
        if identifier in Plot._instances:
            raise ValueError("Plot with identifier "
                             + "'{}' already exists!".format(identifier))
        Plot._instances[identifier] = self

    def __getstate__(self):
        state = copy.deepcopy(self._state)
        state["identifier"] = self.identifier
        return state

    def __repr__(self):
        repre = "<Pipeline Plot '{}' at {}>".format(self.identifier,
                                                    hex(id(self)))
        return repre

    def __setstate__(self, state):
        state = copy.deepcopy(state)
        if self.identifier != state["identifier"]:
            raise ValueError("Identifier mismatch: '{}' vs. '{}'".format(
                self.identifier, state["identifier"]))
        # disallow nan-values
        if np.any(np.isinf(state["general"]["range x"])):
            state["general"]["range x"] = [0, 0]
        if np.any(np.isinf(state["general"]["range y"])):
            state["general"]["range y"] = [0, 0]
        self._state = state

    @staticmethod
    def get_instances():
        return Plot._instances

    @staticmethod
    def get_plot(identifier):
        """Get the plot with the given identifier.

        Notes
        -----
        Creates the plot if it does not exist.
        """
        if identifier in Plot._instances:
            f = Plot._instances[identifier]
        else:
            f = Plot(identifier=identifier)
        return f

    @property
    def hash(self):
        """Return the hash of the plot"""
        return hashobj(self.__getstate__())

    @property
    def name(self):
        return self._state["layout"]["name"]

    @name.setter
    def name(self, value):
        self._state["layout"]["name"] = value
