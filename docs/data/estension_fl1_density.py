def compute_fluorescence_density_fl1(rtdc_ds):
    """Compute fluorescence area divided by cell volume [a.u./µm³]"""
    fl1_density = rtdc_ds["fl1_area"] / rtdc_ds["volume"]
    return {"fl1_density": fl1_density}


info = {
    "method": compute_fluorescence_density_fl1,
    "description": "fluorescence density 1",
    "long description":
        "Fluorescence density puts the integrated fluorescence signal "
        + "in relation to the object volume. This plugin feature computes "
        + "the fluorescence density for channel 1.",
    "feature names": ["fl1_density"],
    "feature labels": ["FL-1 density [a.u.]"],
    "features required": ["fl1_area", "volume"],
    "version": "0.1.0",
}
