"""Convenience methods to retrieve meta data from .rtdc files"""
import functools
import pathlib

import dclab

import numpy as np


class dataset_monitoring_lru_cache:
    """Decorator for caching RT-DC data extracted from DCOR or files

    This is a modification of dclab.util.file_monitoring_lru_cache
    with an exception that when the `path` starts with "https://",
    then caching is done as well.
    """

    def __init__(self, maxsize=100):
        self.lru_cache = functools.lru_cache(maxsize=maxsize)
        self.cached_wrapper = None

    def __call__(self, func):
        @self.lru_cache
        def cached_wrapper(path, path_stats, *args, **kwargs):
            assert path_stats, "We need stat for validating the cache"
            return func(path, *args, **kwargs)

        @functools.wraps(func)
        def wrapper(path, *args, **kwargs):
            local_path = pathlib.Path(path)
            if local_path.exists():
                full_path = local_path.resolve()
                path_stat = full_path.stat()
                return cached_wrapper(
                    path=full_path,
                    path_stats=(path_stat.st_mtime_ns, path_stat.st_size),
                    *args,
                    **kwargs)
            elif isinstance(path, str) and path.startswith("https://"):
                # DCOR metadata does not change
                return cached_wrapper(
                    path=path,
                    path_stats="placeholder",
                    *args,
                    **kwargs)
            else:
                return func(path, *args, **kwargs)

        wrapper.cache_clear = cached_wrapper.cache_clear
        wrapper.cache_info = cached_wrapper.cache_info

        return wrapper


def get_info(path, section, key):
    config = get_rtdc_config(path)
    return config[section][key]


def get_repr(path, append_path=False):
    """representative string of a dataset"""
    exp = get_rtdc_config(path)["experiment"]
    rep = "{} #{} ({} {})".format(exp["sample"],
                                  exp["run index"],
                                  exp["date"],
                                  exp["time"])
    if append_path:
        rep += "\n{}".format(path)
    return rep


@dataset_monitoring_lru_cache(maxsize=100)
def get_rtdc_config(path):
    with dclab.new_dataset(path) as ds:
        config = ds.config.copy()
    return config


@dataset_monitoring_lru_cache(maxsize=100)
def get_rtdc_features(path, scalar=True, only_loaded=False):
    """Return available features in a dataset"""
    av_feat = []
    with dclab.new_dataset(path) as ds:
        if scalar:
            features = ds.features_scalar
        else:
            features = ds.features
        for feat in features:
            if only_loaded:
                if feat in ds.features_loaded:
                    av_feat.append(feat)
            else:
                if feat in ds:
                    av_feat.append(feat)
    return av_feat


def get_rtdc_features_bulk(paths, scalar=True):
    """Return available features for a list of dataset paths"""
    features = []
    for pp in paths:
        features += get_rtdc_features(path=pp, scalar=scalar)
    return sorted(set(features))


@dataset_monitoring_lru_cache(maxsize=10000)
def get_rtdc_features_minmax(path, *features):
    """Return dict with min/max of scalar features in a dataset"""
    mmdict = {}
    with dclab.new_dataset(path) as ds:
        if len(features) == 0:
            features = ds.features_loaded
        for feat in features:
            assert dclab.dfn.scalar_feature_exists(feat)
            if feat in ds:
                mmdict[feat] = np.min(ds[feat]), np.max(ds[feat])
    return mmdict


def get_rtdc_features_minmax_bulk(paths, features=None):
    """Perform `get_rtdc_features_minmax` on a list of paths

    Parameters
    ----------
    paths: list of str or list of pathlib.Path
        Paths to measurement files
    features: list of str or empty list
        Names of the features to compute the min/max values for.
        If empty, all loaded features will be used.
    """
    if features is None:
        features = []
    mmdict = {}
    for pp in paths:
        mmdi = get_rtdc_features_minmax(pp, *features)
        for feat in mmdi:
            if feat in mmdict:
                fmin = min(mmdict[feat][0], mmdi[feat][0])
                fmax = max(mmdict[feat][1], mmdi[feat][1])
                mmdict[feat] = (fmin, fmax)
            else:
                mmdict[feat] = mmdi[feat]
    return mmdict
