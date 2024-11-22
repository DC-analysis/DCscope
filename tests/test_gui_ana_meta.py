import pytest

import numpy as np

from shapeout2.gui.analysis import ana_meta


@pytest.mark.parametrize("input,output", [
    (0.0, "0.0 µL/s"),
    (np.float64(4.9e-323), "0.0 µL/s"),
    (12300.212, "12300.21 µL/s"),
    (0.0002546, "0.000255 µL/s"),
])
def test_format_config_key_value_numbers(input, output):
    act = ana_meta.format_config_key_value("setup", "flow rate", input)
    assert act[1] == output
