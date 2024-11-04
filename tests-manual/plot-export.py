"""Referemce plotting image tests"""
from unittest import mock
import pathlib
import sys

from PyQt6 import QtCore
from PyQt6.QtWidgets import QApplication
from shapeout2.gui import export
from shapeout2.gui.main import ShapeOut2


here = pathlib.Path(__file__).parent

# instantiate Shape-Out
app = QApplication(sys.argv)
QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.C))
mw = ShapeOut2()

# load session
mw.on_action_open(here / "plot-export.so2")
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)

# scatter-and-contour-export-png
with mock.patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName") as gsfn:
    gsfn.return_value = \
        (str(here / "plot-export_scatter-and-contour-export-png_actual.png"),
         ".png")
    # create export dialog manually
    dlg = export.ExportPlot(mw, pipeline=mw.pipeline)
    # select a single plot to export
    plot_id = mw.pipeline.plot_ids[0]
    plot_index = dlg.comboBox_plot.findData(plot_id)
    dlg.comboBox_plot.setCurrentIndex(plot_index)
    dlg.export_plots()


# scatter-long-title-export
with mock.patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName") as gsfn:
    gsfn.return_value = \
        (str(here / "plot-export_scatter-long-title-export-png_actual.png"),
         ".png")
    # create export dialog manually
    dlg = export.ExportPlot(mw, pipeline=mw.pipeline)
    # select a single plot to export
    plot_id = mw.pipeline.plot_ids[1]
    plot_index = dlg.comboBox_plot.findData(plot_id)
    dlg.comboBox_plot.setCurrentIndex(plot_index)
    dlg.export_plots()


# scatter-and-contour-export-svg
with mock.patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName") as gsfn:
    gsfn.return_value = \
        (str(here / "plot-export_scatter-and-contour-export-svg_actual.svg"),
         ".svg")
    # create export dialog manually
    dlg = export.ExportPlot(mw, pipeline=mw.pipeline)
    dlg.comboBox_fmt.setCurrentIndex(1)
    # select a single plot to export
    plot_id = mw.pipeline.plot_ids[0]
    plot_index = dlg.comboBox_plot.findData(plot_id)
    dlg.comboBox_plot.setCurrentIndex(plot_index)
    dlg.export_plots()


# log-large-points-export-png
with mock.patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName") as gsfn:
    gsfn.return_value = \
        (str(here / "plot-export_log-large-points-export-png_actual.png"),
         ".png")
    # create export dialog manually
    dlg = export.ExportPlot(mw, pipeline=mw.pipeline)
    # select a single plot to export
    plot_id = mw.pipeline.plot_ids[2]
    plot_index = dlg.comboBox_plot.findData(plot_id)
    dlg.comboBox_plot.setCurrentIndex(plot_index)
    dlg.export_plots()


# log-large-points-export-svg
with mock.patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName") as gsfn:
    gsfn.return_value = \
        (str(here / "plot-export_log-large-points-export-svg_actual.svg"),
         ".svg")
    # create export dialog manually
    dlg = export.ExportPlot(mw, pipeline=mw.pipeline)
    dlg.comboBox_fmt.setCurrentIndex(1)
    # select a single plot to export
    plot_id = mw.pipeline.plot_ids[2]
    plot_index = dlg.comboBox_plot.findData(plot_id)
    dlg.comboBox_plot.setCurrentIndex(plot_index)
    dlg.export_plots()


# scatter-and-contour-subplot-export-png
plot1 = mw.subwindows_plots["Plot_1"].widget()
plot1_subplot1 = plot1.plot_items[0]
plot1_subplot2 = plot1.plot_items[1]
plot1_subplot1.perform_export(str(
    here / "plot-export_scatter-and-contour-subplot1-export-png_actual.png"))
plot1_subplot2.perform_export(str(
    here / "plot-export_scatter-and-contour-subplot2-export-png_actual.png"))
# scatter-and-contour-subplot-export-svg
plot1_subplot1.perform_export(str(
    here / "plot-export_scatter-and-contour-subplot1-export-svg_actual.svg"))
plot1_subplot2.perform_export(str(
    here / "plot-export_scatter-and-contour-subplot2-export-svg_actual.svg"))
