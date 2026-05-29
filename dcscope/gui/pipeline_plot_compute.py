"""Methods that can run in background threads

The idea is you can only change the pyqtgraph plots in the main loop,
but you can prepare the plotted data (e.g. KDE computation) in the
background, keeping the UI responsive.
"""
from dclab.kde import KernelDensityEstimator
from dclab.kde.smooth_contour import compute_contour_opening_angles
import numpy as np
import pyqtgraph as pg

from .widgets import get_colormap


def compute_contours_from_state(plot_state, rtdc_ds, slot_state=None):
    """Compute th econtour given the plot state and a dataset

    `slot_state` is not used, but required for correctly assigning a
    contour to a slot in the pipeline plot TaskManager workflow.
    """
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
    if (np.allclose(np.abs(angles[0]), np.pi / 2)
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
        slot_state: dict | None = None,
        ):
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
