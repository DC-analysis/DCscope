"""Methods that can run in background threads

The idea is you can only change the pyqtgraph plots in the main loop,
but you can prepare the plotted data (e.g. KDE computation) in the
background, keeping the UI responsive.
"""
import warnings

from dclab.features.emodulus import viscosity
from dclab.kde import KernelDensityEstimator
from dclab.kde.smooth_contour import compute_contour_opening_angles
import numpy as np
import pyqtgraph as pg

from ..pipeline import Pipeline

from .widgets import get_colormap


def compute_contours_from_state(
        plot_state,
        rtdc_ds,
        pipeline: Pipeline | None = None,
        slot_state: dict | None = None,
        ):
    """Compute the contours given the plot state and a dataset

    If `pipeline` is specified, then the plot dictionary is taken
    from `pipeline.get_plot(plot_state["identifier"])`.

    `slot_state` is not used, but required for correctly assigning a
    contour to a slot in the pipeline plot TaskManager workflow.
    """
    if pipeline is not None:
        # get the latest plot state
        plot = pipeline.get_plot(plot_state["identifier"])
        plot_state = plot.__getstate__()

    gen = plot_state["general"]
    con = plot_state["contour"]
    rtdc_ds.apply_filter()
    # compute contour plot data
    kde_instance = KernelDensityEstimator(rtdc_ds=rtdc_ds)
    contours = kde_instance.get_contour_lines(
        xax=gen["axis x"],
        yax=gen["axis y"],
        xacc=gen["spacing x"],
        yacc=gen["spacing y"],
        xscale=gen["scale x"],
        yscale=gen["scale y"],
        kde_type=gen["kde"],
        quantiles=[p/100 for p in con["percentiles"]],
    )
    return contours


def compute_contour_reliable(plot_state, contour, thresh_ang=np.deg2rad(23)):
    """Determine whether contour is reliable or not"""
    # Compute the opening angle for each point of the
    # contour and take the point with the largest opening angle.
    angles = compute_contour_opening_angles(
        contour=contour,
        xrange=plot_state["general"]["range x"],
        yrange=plot_state["general"]["range y"],
        xscale=plot_state["general"]["scale x"],
        yscale=plot_state["general"]["scale y"],
    )
    if (np.allclose(np.abs(angles[0]), np.pi / 2, atol=0.001, rtol=0)
            and np.all(angles[1:6] == 0)):
        # We have probably encountered a contour at the boundary
        # of the image. It looks like this is ok.
        reliable = True
    elif len(angles) > 100:
        # The contour is long enough to be trusted.
        reliable = True
    else:
        reliable = np.max(np.abs(angles)) <= thresh_ang
    return reliable


def compute_scatter_data_from_state(
        plot_state,
        rtdc_ds,
        pipeline: Pipeline | None = None,
        slot_state: dict | None = None,
        ):
    """Compute scatte rplot data given the plot state and a dataset

    If `pipeline` is specified, then the plot dictionary is taken
    from `pipeline.get_plot(plot_state["identifier"])`.

    `slot_state` is not used, but required for correctly assigning a
    contour to a slot in the pipeline plot TaskManager workflow.
    """
    if pipeline is not None:
        # get the latest plot state
        plot = pipeline.get_plot(plot_state["identifier"])
        plot_state = plot.__getstate__()

    gen = plot_state["general"]
    sca = plot_state["scatter"]
    slot_state = slot_state or {}
    rtdc_ds.apply_filter()

    # get downsampled list of points for scatter plot
    x, y, idx = rtdc_ds.get_downsampled_scatter(
        downsample=sca["downsample"] * sca["downsampling value"],
        xax=gen["axis x"],
        yax=gen["axis y"],
        xscale=gen["scale x"],
        yscale=gen["scale y"],
        remove_invalid=True,
        ret_mask=True)

    # create KDE instance
    kde_instance = KernelDensityEstimator(rtdc_ds=rtdc_ds)

    # interpolate the KDE at the specified positions
    kde = kde_instance.get_at(
        positions=(x, y),
        xax=gen["axis x"],
        yax=gen["axis y"],
        kde_type=gen["kde"],
        xscale=gen["scale x"],
        yscale=gen["scale y"],
        xacc=gen["spacing x"],
        yacc=gen["spacing y"],
    )

    if kde.size:
        kde_nan = np.isnan(kde)

        if np.any(~kde_nan):
            # We have non-nan values that we can normalize.
            kde_min = np.nanmin(kde)
            kde_max = np.nanmax(kde)
            if not np.any(np.isnan([kde_min, kde_max])) and kde_min != kde_max:
                kde -= kde_min
                kde /= (kde_max - kde_min)

        if np.any(kde_nan):
            # Set all nan-values to zero so user can see the dots
            kde[kde_nan] = 0

    # brush
    cmap = get_colormap(sca["colormap"])
    if sca["marker hue"] == "kde":
        # Note: we don't expand the density to [0, 1], because the
        # colorbar will show "density" and because we don't want to
        # compute the density in this function and not someplace else.
        brush = [cmap.mapToQColor(k) for k in kde]
        # Note, colors could also be digitized (does not seem to be faster):
        # cbin = np.linspace(0, 1, 1000)
        # dig = np.digitize(kde, cbin)
        # for idx in dig:
        #     brush.append(cmap.mapToQColor(cbin[idx]))
    elif sca["marker hue"] == "feature":
        brush = []
        feat = np.asarray(rtdc_ds[sca["hue feature"]][idx], dtype=float)
        f_min = sca.get("hue min") or np.min(feat)
        f_max = sca.get("hue max") or np.max(feat)
        feat -= f_min
        feat /= f_max - f_min
        for f in feat:
            if np.isnan(f):
                brush.append(pg.mkColor("#FF0000"))
            else:
                brush.append(cmap.mapToQColor(f))
    elif sca["marker hue"] == "dataset":
        alpha = int(sca["marker alpha"] * 255)
        colord = pg.mkColor(slot_state.get("color", "k"))
        colord.setAlpha(alpha)
        brush = pg.mkBrush(colord)
    else:
        alpha = int(sca["marker alpha"] * 255)
        colork = pg.mkColor("#000000")
        colork.setAlpha(alpha)
        brush = pg.mkBrush(colork)

    return x, y, kde, idx, brush


def get_emodulus_warnings(rtdc_ds, plot_state):
    """Return warnings about inaccurate Young's modulus data in a plot (#144)

    The warnings correspond to those that dclab issues when computing
    the Young's modulus. Since dclab caches the Young's modulus, its
    warnings are only issued once, so they are deduced here:

    - more than 10% of the events are not covered by the look-up table
      (:class:`dclab.features.emodulus.YoungsModulusLookupTableExceededWarning`)
    - the temperature is outside the valid range of the viscosity model
      (:class:`dclab.features.emodulus.viscosity.TemperatureOutOfRangeWarning`)

    Parameters
    ----------
    rtdc_ds: dclab.rtdc_dataset.RTDCBase
        Dataset with filters applied
    plot_state: dict
        Plot state; warnings are only returned if the Young's modulus
        is plotted (axes or scatter plot hue)

    Returns
    -------
    messages: list of tuple
        Short messages for display in the plot and detailed
        descriptions (e.g. for tooltips)
    """
    gen = plot_state["general"]
    sca = plot_state["scatter"]
    features = [gen["axis x"], gen["axis y"]]
    if sca["enabled"] and sca["marker hue"] == "feature":
        features.append(sca["hue feature"])
    if "emodulus" not in features or "emodulus" not in rtdc_ds:
        return []

    messages = []
    filt = rtdc_ds.filter.all
    emod = np.asarray(rtdc_ds["emodulus"][filt])
    if emod.size:
        nan_fraction = np.mean(np.isnan(emod))
        if nan_fraction > 0.1:
            lut = rtdc_ds.config["calculation"].get("emodulus lut", "")
            messages.append((
                f"{nan_fraction:.0%} of events outside LUT",
                f"The Young's modulus could not be computed for "
                f"{nan_fraction:.0%} of the events, because they are not "
                f"covered by the look-up table '{lut}'."))

    # temperature range of the viscosity model (known media only)
    calc = rtdc_ds.config["calculation"]
    medium = calc.get("emodulus medium", "other")
    if medium in viscosity.KNOWN_MEDIA:
        if "emodulus temperature" in calc:
            temperature = calc["emodulus temperature"]
        elif "temp" in rtdc_ds:
            temperature = np.asarray(rtdc_ds["temp"][filt])
        else:
            temperature = None
        if temperature is not None and np.size(temperature):
            with warnings.catch_warnings(record=True) as ws:
                warnings.simplefilter("always")
                viscosity.get_viscosity(
                    medium=medium,
                    channel_width=rtdc_ds.config["setup"]["channel width"],
                    flow_rate=rtdc_ds.config["setup"]["flow rate"],
                    temperature=temperature,
                    model=calc.get("emodulus viscosity model",
                                   "herold-2017"),
                )
            for w in ws:
                if issubclass(w.category,
                              viscosity.TemperatureOutOfRangeWarning):
                    messages.append((
                        "Temperature out of range",
                        f"Young's modulus: {w.message}"))
                    break
    return messages
