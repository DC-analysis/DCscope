from typing import Literal

import numpy as np
import pyqtgraph as pg
from scipy.ndimage import binary_erosion


cmap_pha: pg.ColorMap = pg.colormap.get('CET-D1A', skipCache=True)
cmap_pha_with_black: pg.ColorMap = pg.colormap.get('CET-D1A', skipCache=True)
cmap_pha_with_black.color[0] = [0, 0, 0, 1]


@staticmethod
def convert_to_rgb(cell_img):
    """Add a third axis of length 3 with copies"""
    cell_img = cell_img.reshape(
        cell_img.shape[0], cell_img.shape[1], 1)
    return np.repeat(cell_img, 3, axis=2)


def get_rgb_image(data: dict,
                  feat: str,
                  zoom: bool = False,
                  draw_contour: bool = False,
                  auto_contrast: bool = False,
                  subtract_background: bool = False,
                  ) -> tuple[np.ndarray, float, float, pg.ColorMap | None]:
    """Return a pretty visualization of image data"""
    if feat == "image":
        cmap = None
        cell_img, vmin, vmax = prepare_event_image_image(
            data,
            zoom=zoom,
            draw_contour=draw_contour,
            auto_contrast=auto_contrast,
            subtract_background=subtract_background,
        )
    elif feat == "qpi_amp":
        cmap = None
        cell_img, vmin, vmax = prepare_event_image_qpi_amp(
            data,
            zoom=zoom,
            draw_contour=draw_contour,
            auto_contrast=auto_contrast,
        )
    elif feat == "qpi_pha":
        cell_img, vmin, vmax, cmap = prepare_event_image_qpi_pha(
            data,
            zoom=zoom,
            draw_contour=draw_contour,
            auto_contrast=auto_contrast,
        )
    else:
        raise KeyError(f"Unknown image feature '{feat}'")

    return cell_img, vmin, vmax, cmap


def image_insert_contour(cell_img: np.ndarray,
                         mask: np.ndarray,
                         cmap_levels: tuple[float, float],
                         contour_style: Literal["red", "lowest-level"],
                         ):
    """Insert contour data in an image"""
    # Compute contour image from mask. If you are wondering
    # whether this is kosher, please take a look at issue #76:
    # https://github.com/DC-analysis/dclab/issues/76
    cont = mask ^ binary_erosion(mask)
    if contour_style == "red":
        vmin, vmax = cmap_levels
        # draw red contour for grayscale images
        ch_red = vmin + (vmax - vmin) * 0.7
        ch_other = vmin
        # assign channel values for contour
        cell_img[cont, 0] = ch_red
        cell_img[cont, 1] = ch_other
        cell_img[cont, 2] = ch_other
    elif contour_style == "lowest-level":
        # use the lowest value from the colormap
        # (used for e.g. phase images)
        cell_img[cont] = cmap_levels[0]

    return cell_img


def image_zoom(cell_img, mask):
    """Zoom in on the image"""
    xv, yv = np.where(mask)
    idminx = xv.min() - 5
    idminy = yv.min() - 5
    idmaxx = xv.max() + 5
    idmaxy = yv.max() + 5
    idminx = idminx if idminx >= 0 else 0
    idminy = idminy if idminy >= 0 else 0
    shx, shy = mask.shape
    idmaxx = idmaxx if idmaxx < shx else shx
    idmaxy = idmaxy if idmaxy < shy else shy
    return cell_img[idminx:idmaxx, idminy:idmaxy]


def prepare_event_image_image(
        data,
        zoom: bool = False,
        draw_contour: bool = False,
        auto_contrast: bool = False,
        subtract_background: bool = False,
) -> tuple[np.ndarray, float, float]:
    """Prepare to draw a regular image event"""
    cell_img = data["image"]

    if zoom and "mask" in data:
        cell_img = image_zoom(cell_img, data["mask"])

    # apply background correction
    if subtract_background and "image_bg" in data:

        bgimg = data["image_bg"].astype(np.int16)
        if zoom and "mask" in data:
            bgimg = image_zoom(bgimg, data["mask"])

        cell_img = cell_img.astype(np.int16)
        cell_img = cell_img - bgimg + int(np.mean(bgimg))

    # automatic contrast
    if auto_contrast:
        vmin, vmax = cell_img.min(), cell_img.max()
    else:
        vmin, vmax = (0, 255)

    cell_img = convert_to_rgb(cell_img)

    if draw_contour and "mask" in data:
        mask = data["mask"]
        if zoom:
            mask = image_zoom(mask, mask)

        cell_img = image_insert_contour(
            cell_img,
            mask,
            cmap_levels=(vmin, vmax),
            contour_style="red",
        )

    return cell_img, vmin, vmax


def prepare_event_image_qpi_amp(
        data,
        zoom: bool = False,
        draw_contour: bool = False,
        auto_contrast: bool = False,
) -> tuple[np.ndarray, float, float]:
    """Prepare to draw a QPI amplitude event image"""
    cell_img = data["qpi_amp"]

    if zoom and "mask" in data:
        cell_img = image_zoom(cell_img, data["mask"])

    if auto_contrast:
        vmin, vmax = cell_img.min(), cell_img.max()
    else:
        vmin, vmax = (0, 2)

    cell_img = convert_to_rgb(cell_img)

    if draw_contour and "mask" in data:
        mask = data["mask"]
        if zoom:
            mask = image_zoom(mask, mask)

        cell_img = image_insert_contour(
            cell_img,
            mask,
            cmap_levels=(vmin, vmax),
            contour_style="red",
        )

    return cell_img, vmin, vmax


def prepare_event_image_qpi_pha(
        data,
        zoom: bool = False,
        draw_contour: bool = False,
        auto_contrast: bool = False,
) -> tuple[np.ndarray, float, float, pg.ColorMap]:
    """Prepare to draw a QPI phase event image"""
    cell_img = np.copy(data["qpi_pha"])

    if zoom and "mask" in data:
        cell_img = image_zoom(cell_img, data["mask"])

    if auto_contrast:
        # phase values centered around zero
        vmin_abs, vmax_abs = np.abs(cell_img.min()), np.abs(cell_img.max())
        v_largest = max(vmax_abs, vmin_abs)
        vmin, vmax = -v_largest, v_largest
    else:
        vmin, vmax = (-3.14, 3.14)

    if draw_contour and "mask" in data:
        # offset required for auto-contrast with contour
        # two times the contrast range, divided by the cmap length
        # this essentially adds a cmap point for our contour
        offset = 2 * ((vmax - vmin) / len(cmap_pha.color))
        vmin -= offset

        mask = data["mask"]
        if zoom:
            mask = image_zoom(mask, mask)

        cell_img = image_insert_contour(
            cell_img,
            mask,
            cmap_levels=(vmin, vmax),
            contour_style="lowest-level",
        )
        cmap = cmap_pha_with_black
    else:
        cmap = cmap_pha

    return cell_img, vmin, vmax, cmap
