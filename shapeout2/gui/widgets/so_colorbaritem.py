import pyqtgraph as pg


class ShapeOutColorBarItem(pg.ColorBarItem):
    def __init__(self, yoffset, height, label, colorMap, *args, **kwargs):
        """pg.ColorBarItem modified for Shape-Out

        - Added option to define height
        - translate the colorbar so that it is aligned with the plot
        - show the label on the right-hand axis
        - increase the contents margins
        """
        super(ShapeOutColorBarItem, self).__init__(
            colorMap=colorMap,
            # TODO: Removing `cmap=colorMap` results in grayscale colormaps.
            # https://github.com/ZELLMECHANIK-DRESDEN/ShapeOut2/issues/109
            # This does not make sense at all. But maybe some mysteries are
            # meant to stay hidden indefinitely. Maybe in July 2022, when
            # pyqtgraph drops the "cmap" argument, it will just work...
            cmap=colorMap,
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
