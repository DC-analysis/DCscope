import pathlib

from dcscope import pipeline


def test_filtering_change_get_dataset():
    path = pathlib.Path(__file__).parent / "data" / "calibration_beads_47.rtdc"

    # initialize
    slot = pipeline.Dataslot(path)
    ds = slot.get_dataset()
    assert len(ds) == 47
    ray = pipeline.FilterRay(slot)

    filt1 = pipeline.Filter()
    filt1.limit_events = [True, 4]

    ray.set_filters([filt1])
    ds1 = ray.get_dataset()
    assert len(ds1) == 4

    filt1.limit_events = [False, 4]
    ds2 = ray.get_dataset()
    assert len(ds2) == 47

    filt1.limit_events = [True, 4]
    ds3 = ray.get_dataset()
    assert len(ds3) == 4

    filt1.limit_events = [False, 4]
    ds4 = ray.get_dataset()
    assert len(ds4) == 47


def test_filtering_change_get_final_child():
    path = pathlib.Path(__file__).parent / "data" / "calibration_beads_47.rtdc"

    # initialize
    slot = pipeline.Dataslot(path)
    ds = slot.get_dataset()
    assert len(ds) == 47
    ray = pipeline.FilterRay(slot)

    filt1 = pipeline.Filter()
    filt1.limit_events = [True, 4]

    ray.set_filters([filt1])
    ds1 = ray.get_final_child()
    assert len(ds1) == 4

    filt1.limit_events = [False, 4]
    ds2 = ray.get_final_child()
    assert len(ds2) == 47

    filt1.limit_events = [True, 4]
    ds3 = ray.get_final_child()
    assert len(ds3) == 4

    filt1.limit_events = [False, 4]
    ds4 = ray.get_final_child()
    assert len(ds4) == 47


def test_filtering_change_with_pipeline():
    path = pathlib.Path(__file__).parent / "data" / "calibration_beads_47.rtdc"

    # initialize
    pipe = pipeline.Pipeline()
    pipe.add_slot(path=path)
    filt1 = pipeline.Filter()
    pipe.add_filter(filt1)
    ds = pipe.get_dataset(0)
    assert len(ds) == 47

    slot_id = pipe.slot_ids[0]
    filt_id = filt1.identifier

    pipe.set_element_active(slot_id, filt_id, True)

    assert pipe.filter_ids == [filt_id]
    filters = pipe.get_filters_for_slot(slot_id=slot_id,
                                        max_filter_index=-1)
    assert filters[0] == filt1

    filt1.limit_events = [True, 4]

    assert pipe.element_states[slot_id][filt_id]
    assert pipe.get_filters_for_slot(slot_id=slot_id,
                                     max_filter_index=-1) == [filt1]
    ds1 = pipe.get_dataset(0)
    assert len(ds1) == 4

    pipe.set_element_active(slot_id, filt_id, False)
    assert not pipe.element_states[slot_id][filt_id]
    assert pipe.get_filters_for_slot(slot_id=slot_id,
                                     max_filter_index=-1) == []
    ds2 = pipe.get_dataset(0)
    assert len(ds2) == 47

    pipe.set_element_active(slot_id, filt_id, True)
    assert pipe.element_states[slot_id][filt_id]
    assert len(pipe.filters) == 1
    assert pipe.get_filters_for_slot(slot_id=slot_id,
                                     max_filter_index=-1) == [filt1]
    ray = pipe.get_ray(slot_id)
    ray.set_filters([filt1])
    ds3a = ray.get_dataset()
    assert len(ds3a) == 4
    ds3b = pipe.get_dataset(0)
    assert len(ds3b) == 4

    pipe.set_element_active(slot_id, filt_id, False)
    ds4 = pipe.get_dataset(0)
    assert len(ds4) == 47
