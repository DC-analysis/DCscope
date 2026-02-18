import pathlib

import numpy as np
from dcscope import pipeline


def test_get_heredity():
    path = pathlib.Path(__file__).parent / "data" / "calibration_beads_47.rtdc"

    # initialize
    slot = pipeline.Dataslot(path)
    ds = slot.get_dataset()
    ray = pipeline.FilterRay(slot)

    # come up with a few filters
    # this does some simple things
    filt1 = pipeline.Filter()
    filt1.boxdict["area_um"] = {"start": np.min(ds["area_um"]),
                                "end": np.mean(ds["area_um"]),
                                "active": True}

    # this one does nothing (and should be ignored)
    fign2 = pipeline.Filter()
    fign2.filter_used = False

    # another one with simple things
    filt3 = pipeline.Filter()
    filt3.boxdict["deform"] = {"start": np.min(ds["deform"]),
                               "end": np.mean(ds["deform"]),
                               "active": True}

    # simple
    ray.set_filters([filt1, fign2])
    ds1 = ray.get_dataset()
    assert ray._generation == 0

    # leaving out a filter that does nothing will not change anything
    ray.set_filters([filt1])
    ds2 = ray.get_dataset()
    assert ray._generation == 0
    assert ds1 is ds2

    # changing the order will not change anything either
    ray.set_filters([fign2, filt1])
    ds3 = ray.get_dataset()
    assert ray._generation == 0
    assert ds1 is ds3

    # adding a new filter will change the dataset
    ray.set_filters([filt1, fign2, filt3])
    ds4 = ray.get_dataset()
    assert ray._generation == 0
    assert ds1 is not ds4

    assert ds1 is ds4.hparent

    # going back does not increment the generation...
    ray.set_filters([filt1, fign2])
    ds5 = ray.get_dataset()
    assert ray._generation == 0
    assert ds1 is ds5

    # ...but changing the order is
    ray.set_filters([filt3, filt1, fign2])
    ds5 = ray.get_dataset()
    assert ray._generation == 1
    assert ds1 is not ds5
    assert ds3 is not ds5

    # and then again, when we remove a filter, we get something different
    ray.set_filters([filt3, filt1])
    ds6 = ray.get_dataset()
    assert ray._generation == 1
    assert ds1 is not ds6
    assert ds5 is ds6  # b/c filt2 does nothing


def test_filtering():
    path = pathlib.Path(__file__).parent / "data" / "calibration_beads_47.rtdc"

    # initialize
    slot = pipeline.Dataslot(path)
    ds = slot.get_dataset()
    assert len(ds) == 47
    ray = pipeline.FilterRay(slot)

    # come up with a few filters
    # this does some simple things
    filt1 = pipeline.Filter()
    filt1.boxdict["area_um"] = {"start": np.min(ds["area_um"]),
                                "end": np.mean(ds["area_um"]),
                                "active": True}

    # this one does nothing (and should be ignored)
    fign2 = pipeline.Filter()
    fign2.filter_used = False

    # another one with simple things
    filt3 = pipeline.Filter()
    filt3.boxdict["deform"] = {"start": np.min(ds["deform"]),
                               "end": np.mean(ds["deform"]),
                               "active": True}

    ray.set_filters([fign2])
    ds1 = ray.get_dataset()
    assert len(ds1) == 47, "filter two, nothing happens"
    assert np.sum(ds1.filter.all) == len(ds)

    ray.set_filters([fign2, filt1])
    ds2 = ray.get_dataset()
    assert len(ds2) == 22, "filter two applied first, no events removed"
    assert np.sum(ds2.filter.all) == 22

    ray.set_filters([filt1, filt3])
    ds3 = ray.get_dataset()
    assert len(ds3) == 12, "filter one applied first"
    assert np.sum(ds3.filter.all) == 12

    ray.set_filters([filt1, fign2])
    ds4 = ray.get_dataset()
    assert len(ds4) == 22, "filter one applied first, filter two ignored"
    assert np.sum(ds4.filter.all) == 22


def test_remove_filter():
    path = pathlib.Path(__file__).parent / "data" / "calibration_beads_47.rtdc"

    # initialize
    slot = pipeline.Dataslot(path)
    ds = slot.get_dataset()
    assert len(ds) == 47
    ray = pipeline.FilterRay(slot)

    # come up with a few filters
    # this does some simple things
    filt1 = pipeline.Filter()
    filt1.boxdict["area_um"] = {"start": np.min(ds["area_um"]),
                                "end": np.mean(ds["area_um"]),
                                "active": True}

    ray.set_filters([filt1])
    ds1 = ray.get_dataset()
    assert len(ds1) == 22
    assert np.sum(ds1.filter.all) == 22

    ray.set_filters([])
    ds2 = ray.get_dataset()
    assert len(ds2) == 47
    assert np.sum(ds2.filter.all) == 47
