import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

from .simple_plot_widget import SimpleViewBox


class SimpleImageView(pg.ImageView):
    """Custom class for data visualization in DCscope"""

    def __init__(self, *args, **kwargs):
        self.view = SimpleImageViewBox()
        super(SimpleImageView, self).__init__(view=self.view,
                                              *args, **kwargs)
        self.view.export.connect(self.on_export)

        # disable pyqtgraph controls we don't need
        self.ui.histogram.hide()
        self.ui.roiBtn.hide()
        self.ui.menuBtn.hide()
        # disable keyboard shortcuts
        self.keyPressEvent = lambda _: None
        self.keyReleaseEvent = lambda _: None

    def on_export(self, suffix):
        assert suffix == "png"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, '', '', 'PNG image (*.png)', '')
        if not path.endswith(".png"):
            path += ".png"

        img = np.require(self.image, np.uint8, 'C')
        height, width, _ = self.image.shape

        qImg = QtGui.QImage(img, width, height, width *
                            3, QtGui.QImage.Format.Format_RGB888)
        qImg.save(path)


class SimpleImageViewBox(SimpleViewBox):
    export = QtCore.pyqtSignal(str)

    def autoRange(self, padding=0, *args, **kwargs):
        super(SimpleImageViewBox, self).autoRange(padding=padding,
                                                  *args,
                                                  **kwargs)

    def raiseContextMenu(self, ev):
        menu = self.menu
        menu.clear()
        menu.addAction("Save event image as PNG",
                       lambda: self.export.emit("png"))

        pos = ev.screenPos()
        menu.popup(QtCore.QPoint(int(pos.x()), int(pos.y())))
        return True
