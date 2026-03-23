from dclab.definitions.feat_const import FEATURES_MONOTONOUS  # noqa: F401
from dclab.rtdc_dataset import feat_anc_core

#: integer-valued features
INTEGER_FEATURES = [
    "fl1_max",
    "fl1_npeaks",
    "fl2_max",
    "fl2_npeaks",
    "fl3_max",
    "fl3_npeaks",
    "frame",
    "index",
    "ml_class",
    "nevents",
]


#: ancillary features that are easily computed
QUICK_FEATURES = feat_anc_core.FEATURES_RAPID
