import pathlib

import dclab

from dcscope.gui import pipeline_plot


datapath = pathlib.Path(__file__).parent / "data"


def test_get_hash_flag():
    rtdc_paths = datapath.glob("*.rtdc")

    assert rtdc_paths

    hash_set = set()
    rtdc_ds_list = []
    expected = []
    for path in rtdc_paths:
        ds = dclab.new_dataset(path)
        # get the hash flag
        pipe_config = ds.config.get("pipeline", {})
        dcnum_hash = pipe_config.get("dcnum hash", None)
        hash_set.add(dcnum_hash)
        expected.append(f"Pipeline {dcnum_hash[:4]}" if dcnum_hash else None)
        rtdc_ds_list.append(ds)

    assert len(hash_set) == 2

    for ds, exp in zip(rtdc_ds_list, expected):
        result = pipeline_plot.get_hash_flag(hash_set, ds)
        assert result == exp


def test_get_hash_flag_datasets_without_hash():
    rtdc_paths = [
        datapath / "artificial_with_image_bg.rtdc",  # No hash
        datapath / "blood_rbc_leukocytes.rtdc",  # No hash
        datapath / "blood_rbc_qpi_data.rtdc",  # No hash
    ]

    assert len(rtdc_paths) == 3

    hash_set = set()
    rtdc_ds_list = []
    expected = []
    for path in rtdc_paths:
        ds = dclab.new_dataset(path)
        # get the hash flag
        pipe_config = ds.config.get("pipeline", {})
        dcnum_hash = pipe_config.get("dcnum hash", None)
        hash_set.add(dcnum_hash)
        expected.append(f"Pipeline {dcnum_hash[:4]}" if dcnum_hash else None)
        rtdc_ds_list.append(ds)

    assert len(hash_set) == 1
    for ds in rtdc_ds_list:
        result = pipeline_plot.get_hash_flag(hash_set, ds)
        assert result is None


def test_get_hash_flag_dataset_with_hash():
    rtdc_paths = [
        datapath / "artificial_with_image_bg.rtdc",  # No hash
        datapath / "blood_rbc_leukocytes.rtdc",  # No hash
        datapath / "naiad-capture_blood_pipeline.rtdc",  # with hash
    ]

    assert len(rtdc_paths) == 3
    hash_set = set()
    rtdc_ds_list = []
    expected = []
    for path in rtdc_paths:
        ds = dclab.new_dataset(path)
        # get the hash flag
        pipe_config = ds.config.get("pipeline", {})
        dcnum_hash = pipe_config.get("dcnum hash", None)
        hash_set.add(dcnum_hash)
        expected.append(f"Pipeline {dcnum_hash[:4]}" if dcnum_hash else None)
        rtdc_ds_list.append(ds)

    assert len(hash_set) == 2
    results = []
    for ds in rtdc_ds_list:
        result = pipeline_plot.get_hash_flag(hash_set, ds)
        results.append(result)

    assert len(results) == 3, "results length should be length of rtdc_paths"

    assert results[0] is None
    assert results[1] is None
    assert results[2] == "Pipeline 1d01"
