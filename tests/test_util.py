from shapeout2 import util


def test_get_valid_filename():
    assert util.get_valid_filename("KLµ123$)]") == "KLu123-))"
    assert util.get_valid_filename("..KLµ123$)].") == "KLu123-))"
    assert util.get_valid_filename(". KLµ123$)]") == "_KLu123-))"
