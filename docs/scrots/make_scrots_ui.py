"""Screenshots for documentation

Data available at https://doi.org/10.6084/m9.figshare.11302595.v1
"""
import pathlib
import sys

import dclab
from PyQt6 import QtCore
from PyQt6.QtWidgets import QApplication
from shapeout2.gui.main import ShapeOut2
from shapeout2 import session

app = QApplication(sys.argv)

QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.C))

mw = ShapeOut2()
mw.settings.setValue("check for updates", 0)
mw.settings.setValue("advanced/user confirm clear", 0)

# build up a session
session.open_session(pathlib.Path(__file__).parent / "scrots.so2",
                     pipeline=mw.pipeline)
mw.reload_pipeline()

# analysis view
mw.on_modify_slot(mw.pipeline.slot_ids[0])
mw.widget_ana_view.repaint()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.widget_ana_view.grab().save("_ui_ana_slot.png")

mw.subwindows["analysis_view"].move(200, 300)

# main window
mw.update()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.grab().save("_ui_main.png")

mw.on_modify_filter(mw.pipeline.filter_ids[0])
mw.widget_ana_view.repaint()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.widget_ana_view.grab().save("_ui_ana_filter.png")

mw.on_modify_plot(mw.pipeline.plot_ids[0])
mw.widget_ana_view.repaint()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.widget_ana_view.grab().save("_ui_ana_plot.png")

mw.widget_ana_view.tabWidget.setCurrentIndex(0)
mw.widget_ana_view.repaint()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.widget_ana_view.grab().save("_ui_ana_meta.png")

# plots
mw.subwindows_plots[mw.pipeline.plot_ids[0]].widget().grab().save(
    "_ui_plot1.png")
mw.subwindows_plots[mw.pipeline.plot_ids[1]].widget().grab().save(
    "_ui_plot2.png")
mw.subwindows_plots[mw.pipeline.plot_ids[2]].widget().grab().save(
    "_ui_plot3.png")

# quick view
me = mw.block_matrix.get_widget(mw.pipeline.slot_ids[1],
                                mw.pipeline.filter_ids[0])
me.update_content(quickview=True)
mw.widget_quick_view.toolButton_settings.toggle()
idx = mw.widget_quick_view.comboBox_x.findData("fl3_max_ctc")
mw.widget_quick_view.comboBox_x.setCurrentIndex(idx)
idy = mw.widget_quick_view.comboBox_y.findData("fl2_max_ctc")
mw.widget_quick_view.comboBox_y.setCurrentIndex(idy)
mw.widget_quick_view.comboBox_xscale.setCurrentIndex(1)
mw.widget_quick_view.comboBox_yscale.setCurrentIndex(1)
mw.widget_quick_view.checkBox_hue.click()
mw.widget_quick_view.toolButton_apply.click()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.widget_quick_view.grab().save("_ui_qv_settings.png")
mw.widget_quick_view.toolButton_event.toggle()
mw.widget_quick_view.spinBox_event.setValue(4829)
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.widget_quick_view.grab().save("_ui_qv_event.png")
# manually create a polygon filter with points from the poly file
mw.widget_quick_view.toolButton_poly.toggle()
pf = dclab.PolygonFilter(filename="CD66+_CD14-.poly")
mw.widget_quick_view.pushButton_poly_create.click()
mw.widget_quick_view.lineEdit_poly.setText("CD66⁺/CD14⁻")
mw.widget_quick_view.widget_scatter.set_poly_points(pf.points)
# show an even
cellimg, imkw = mw.widget_quick_view.get_event_image(
    mw.widget_quick_view.rtdc_ds,
    42)
mw.widget_quick_view.imageView_image_poly.setImage(cellimg, **imkw)
mw.widget_quick_view.imageView_image_poly.show()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.widget_quick_view.grab().save("_ui_qv_poly.png")

# block matrix
mw.block_matrix.setFixedSize(420, 320)
mw.block_matrix.repaint()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.block_matrix.scrollArea_block.grab().save("_ui_block_matrix.png")

mw.close()
