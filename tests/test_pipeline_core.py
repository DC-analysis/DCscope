import copy
import pathlib
import socket

import dclab
import numpy as np
from dcscope import pipeline, session
import pytest


data_path = pathlib.Path(__file__).parent / "data"
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    try:
        s.connect(("www.python.org", 80))
        NET_AVAILABLE = True
    except socket.gaierror:
        # no internet
        NET_AVAILABLE = False


def test_apply_filter_ray():
    path = pathlib.Path(__file__).parent / "data" / "calibration_beads_47.rtdc"

    # initiate the pipeline
    pl = pipeline.Pipeline()
    slot_id = pl.add_slot(path=path)

    # add a filter
    filt_id1 = pl.add_filter()
    filt1 = pl.get_filter(filt_id1)
    amin, amax = pl.get_min_max("area_um")
    filt1.boxdict["area_um"] = {"start": amin,
                                "end": (amin + amax)/2,
                                "active": True}
    pl.set_element_active(slot_id, filt_id1)

    # and another one
    filt_id2 = pl.add_filter()
    filt2 = pl.get_filter(filt_id2)
    dmin, dmax = pl.get_min_max("deform")
    filt2.boxdict["deform"] = {"start": dmin,
                               "end": (dmin + dmax)/2,
                               "active": True}
    pl.set_element_active(slot_id, filt_id2)

    ds_ref = pl.get_dataset(0)  # this will run through the filter ray
    ds0 = dclab.new_dataset(path)
    ds_ext = pl.apply_filter_ray(ds0, slot_id)  # this should do the same thing

    for feat in ds_ref.features_loaded:
        if dclab.dfn.scalar_feature_exists(feat):
            assert np.allclose(ds_ref[feat], ds_ext[feat]), feat
    assert np.all(ds_ref.filter.all == ds_ext.filter.all)


@pytest.mark.skipif(not NET_AVAILABLE, reason="No network connection!")
@pytest.mark.filterwarnings(
    'ignore::dclab.rtdc_dataset.config.WrongConfigurationTypeWarning')
def test_session_dcor():
    pipeline = session.open_session(data_path / "version_2_5_0_dcor_lme4.so2")
    assert pipeline.deduce_reduced_sample_names() == [
        'SSC 16uls rep1',
        'SSC 16uls rep2',
        'MG63 pure 16uls rep1',
        'MG63 pure 16uls rep2',
        'MG63 pure 16uls rep3',
    ]
    # Add the last slot again
    dcor_id = pipeline.slots[-1].path
    pipeline.add_slot(path=dcor_id)
    assert pipeline.deduce_reduced_sample_names() == [
        'SSC 16uls rep1',
        'SSC 16uls rep2',
        'MG63 pure 16uls rep1',
        'MG63 pure 16uls rep2',
        'MG63 pure 16uls rep3',
        'MG63 pure 16uls rep3',
    ]


def test_get_min_max_inf(tmp_path):
    # generate fake dataset
    path = pathlib.Path(__file__).parent / "data" / "calibration_beads_47.rtdc"
    with dclab.new_dataset(path) as ds:
        config = copy.deepcopy(ds.config)

    tmp = tmp_path / "example_filter_inf.rtdc"
    ddict = {"deform": np.linspace(0, .01, 100),
             "area_um": np.linspace(20, 200, 100),
             "area_ratio": np.linspace(1, 1.1, 100)
             }
    ddict["area_ratio"][0] = np.inf
    ddict["area_ratio"][1] = np.nan
    ds2 = dclab.new_dataset(ddict)
    ds2.config.update(config)
    ds2.config["experiment"]["event count"] = 100
    ds2.export.hdf5(tmp, features=["area_um", "deform", "area_ratio"])

    # initiate the pipeline
    pl = pipeline.Pipeline()
    pl.add_slot(path=tmp)
    pl.add_filter()

    # get the current min/max values
    amin, amax = pl.get_min_max("area_ratio")
    assert amin == ds2["area_ratio"][2]
    assert amax == 1.1

    try:
        pathlib.Path(tmp).unlink()
    except BaseException:
        pass


def test_get_min_max_plot():
    """See #22"""
    path = pathlib.Path(__file__).parent / "data" / "calibration_beads_47.rtdc"

    # initiate the pipeline
    pl = pipeline.Pipeline()
    slot_id = pl.add_slot(path=path)

    # add a filter
    filt_id = pl.add_filter()
    filt = pl.get_filter(filt_id)

    # get the current min/max values
    amin, amax = pl.get_min_max("area_um")

    # modify the filter
    filt.boxdict["area_um"] = {"start": amin,
                               "end": (amin + amax)/2,
                               "active": True}

    # make the filter active in the filter ray
    pl.set_element_active(slot_id, filt_id)

    # add a plot
    plot_id = pl.add_plot()
    pl.set_element_active(slot_id, plot_id)

    # get the new min/max values
    amin2, amax2 = pl.get_min_max("area_um", plot_id=plot_id)

    assert amin == amin2
    assert amax2 <= (amin + amax) / 2


if __name__ == "__main__":
    # Run all tests
    loc = locals()
    for key in list(loc.keys()):
        if key.startswith("test_") and hasattr(loc[key], "__call__"):
            loc[key]()
