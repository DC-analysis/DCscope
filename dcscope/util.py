import os.path

# hashobj is imported from several other submodules in DCscope.
# Would we need to add additional functionalities in the future, which
# are not within the scope of dclab, then we can patch this method here.
from dclab.util import hashobj  # noqa: F401


def get_valid_filename(value):
    """
    Return the given string converted to a string that can be used
    for a clean filename.
    """
    ret = ""

    valid = "abcdefghijklmnopqrstuvwxyz" \
            + "ABCDEFGHIJKLMNOPQRSTUVWXYZ" \
            + "0123456789" \
            + "._-()"
    replace = {
        " ": "_",
        "[": "(",
        "]": ")",
        "µ": "u",
    }

    for ch in value:
        if ch in valid:
            ret += ch
        elif ch in replace:
            ret += replace[ch]
        else:
            ret += "-"

    ret = ret.strip(".")
    return ret


def strip_common_prefix_suffix(string_list: list[str]) -> list[str]:
    sl = string_list

    # cut common prefixes
    prefix = os.path.commonprefix(sl)
    sl = [n[len(prefix):] for n in sl]

    # cut common suffixes
    sl = [n[::-1] for n in sl]  # reverse order
    suffix = os.path.commonprefix(sl)
    sl = [n[len(suffix):] for n in sl]

    sl = [n[::-1] for n in sl]  # reverse order
    return sl
