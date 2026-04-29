import pathlib

from PyQt6 import QtCore, QtWidgets
import pyqtgraph.exporters as pge

from ...util import get_valid_filename
from ..pipeline_plot import PipelinePlot
from ..widgets import show_wait_cursor
from .e2plot_ui import Ui_Dialog


EXPORTERS = {
    "png": ["rendered image (*.png)", pge.ImageExporter],
    "svg": ["vector graphics (*.svg)", pge.SVGExporter],
}


class ExportPlot(QtWidgets.QDialog):
    def __init__(self, parent, pipeline, *args, **kwargs):
        super(ExportPlot, self).__init__(parent=parent, *args, **kwargs)

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        # set pipeline
        self.pipeline = pipeline
        # populate combobox plots
        self.ui.comboBox_plot.clear()
        self.ui.comboBox_plot.addItem("All plots", "all")
        for plot in pipeline.plots:
            self.ui.comboBox_plot.addItem(plot.name, plot.identifier)
        # populate combobox format
        self.ui.comboBox_fmt.clear()
        for key in EXPORTERS:
            self.ui.comboBox_fmt.addItem(EXPORTERS[key][0], key)
        # Signals
        self.ui.comboBox_fmt.currentIndexChanged.connect(self.on_format)

    def done(self, r):
        if r:
            self.export_plots()
        super(ExportPlot, self).done(r)

    @show_wait_cursor
    @QtCore.pyqtSlot()
    def export_plots(self):
        """Export the plots according to the current selection

        Returns
        -------
        exported_plots: dict
            dictionary plot identifier: pathlib.Path
        """
        # show dialog
        fmt = self.ui.comboBox_fmt.currentData()
        # keys are plot identifiers, values are paths
        fnames = {}
        if self.ui.comboBox_plot.currentData() == "all":
            path = QtWidgets.QFileDialog.getExistingDirectory(self,
                                                              'Output Folder')
            if path:
                for ii, plot in enumerate(self.pipeline.plots):
                    fn = "SO-plot_{}_{}.{}".format(ii, plot.name, fmt)
                    # remove bad characters from file name
                    fn = get_valid_filename(fn)
                    fnames[plot.identifier] = pathlib.Path(path) / fn
        else:
            pp, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Plot export file name', '',
                self.ui.comboBox_fmt.currentText())
            if pp:
                if not pp.endswith(fmt):
                    pp += "." + fmt
                fnames[self.ui.comboBox_plot.currentData()] = pathlib.Path(pp)

        # get PipelinePlot instance
        for plot_id in fnames:
            pipl = PipelinePlot.instances[plot_id]
            exp = EXPORTERS[fmt][1](pipl.ui.plot_layout.centralWidget)
            if fmt == "png":
                dpi = self.ui.spinBox_dpi.value()
                exp.params["width"] = int(exp.params["width"] / 72 * dpi)
                exp.params["antialias"] = self.ui.checkBox_aa.isChecked()
            pout = str(fnames[plot_id])
            exp.export(pout)

        return fnames

    def on_format(self):
        if self.ui.comboBox_fmt.currentData() == "png":
            self.ui.widget_png.show()
        else:
            self.ui.widget_png.hide()
