from typing import Any

import pyqtgraph as pg
from pyqtgraph.graphicsItems.GradientEditorItem import Gradients


dcs_gradients: dict[str, Any] = dict(Gradients)  # type: ignore
# Register custom colormaps
dcs_gradients["grayblue"] = {
    'ticks': [(0.0, (100, 100, 100, 255)),
              (1.0, (0, 0, 255, 255))],
    'mode': 'rgb',
}

dcs_gradients["graygreen"] = {
    'ticks': [(0.0, (100, 100, 100, 255)),
              (1.0, (0, 180, 0, 255))],
    'mode': 'rgb',
}

dcs_gradients["grayorange"] = {
    'ticks': [(0.0, (100, 100, 100, 255)),
              (1.0, (210, 110, 0, 255))],
    'mode': 'rgb',
}

dcs_gradients["grayred"] = {
    'ticks': [(0.0, (100, 100, 100, 255)),
              (1.0, (200, 0, 0, 255))],
    'mode': 'rgb',
}


def get_colormap(color_map_name):
    cmap_data = dcs_gradients[color_map_name]["ticks"]
    colorMap = pg.ColorMap(*zip(*cmap_data))  # type: ignore
    return colorMap


class DCscopeColorBarItem(pg.ColorBarItem):
    def __init__(self, yoffset, height, label, color_map_name,
                 *args, **kwargs):
        """pg.ColorBarItem modified for DCscope

        - Added option to define height
        - translate the colorbar so that it is aligned with the plot
        - show the label on the right-hand axis
        - increase the contents margins
        """

        super(DCscopeColorBarItem, self).__init__(
            colorMap=get_colormap(color_map_name),
            *args, **kwargs)

        # show label on right side
        self.axis.setLabel(label)

        # increase contents margins
        self.layout.setContentsMargins(7, 0, 7, 0)

        # set correct size and position
        self.setFixedHeight(height)

        tr = self.transform()
        tr.translate(0, yoffset)
        self.setTransform(tr)
