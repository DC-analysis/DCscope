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

#: features that by definition trend over the course of a measurement
SLOPING_FEATURES = [
    "frame",
    "index",
    "index_online",
    "time",
]

#: ancillary features that are easily computed
QUICK_FEATURES = feat_anc_core.FEATURES_RAPID
