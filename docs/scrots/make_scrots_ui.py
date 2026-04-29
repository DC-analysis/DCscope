"""Screenshots for documentation

Data available at https://doi.org/10.6084/m9.figshare.11302595.v1
"""
import pathlib
import sys

import dclab
from PyQt6 import QtCore
from PyQt6.QtWidgets import QApplication
from dcscope.gui.main import DCscope

app = QApplication(sys.argv)

QtCore.QLocale.setDefault(QtCore.QLocale(QtCore.QLocale.Language.C))

mw = DCscope()
mw.settings.setValue("check for updates", 0)
mw.settings.setValue("advanced/user confirm clear", 0)

# build up a session
here = pathlib.Path(__file__).parent
mw.on_action_open(here / "scrots.so2")

# analysis view
mw.on_modify_slot(mw.pipeline.slot_ids[0])
mw.subwindows["analysis_view"].move(200, 300)

# main window
mw.update()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.grab().save("_ui_main.png")

# plots
mw.subwindows_plots[mw.pipeline.plot_ids[0]].widget().grab().save(
    "_ui_plot1.png")
mw.subwindows_plots[mw.pipeline.plot_ids[1]].widget().grab().save(
    "_ui_plot2.png")
mw.subwindows_plots[mw.pipeline.plot_ids[2]].widget().grab().save(
    "_ui_plot3.png")

# quick view
me = mw.ui.block_matrix.get_widget(mw.pipeline.slot_ids[1],
                                mw.pipeline.filter_ids[0])
mw.quickview = True
me.update_content()
mw.widget_quick_view.ui.toolButton_settings.toggle()
idx = mw.widget_quick_view.ui.comboBox_x.findData("fl3_max_ctc")
mw.widget_quick_view.ui.comboBox_x.setCurrentIndex(idx)
idy = mw.widget_quick_view.ui.comboBox_y.findData("fl2_max_ctc")
mw.widget_quick_view.ui.comboBox_y.setCurrentIndex(idy)
mw.widget_quick_view.ui.comboBox_xscale.setCurrentIndex(1)
mw.widget_quick_view.ui.comboBox_yscale.setCurrentIndex(1)
mw.widget_quick_view.ui.checkBox_hue.click()
mw.widget_quick_view.ui.toolButton_apply.click()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.widget_quick_view.grab().save("_ui_qv_settings.png")
mw.widget_quick_view.ui.toolButton_event.toggle()
mw.widget_quick_view.ui.spinBox_event.setValue(4829)
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.widget_quick_view.grab().save("_ui_qv_event.png")
# manually create a polygon filter with points from the poly file
mw.widget_quick_view.on_poly_create()
mw.widget_quick_view.ui.toolButton_poly.toggle()
pf = dclab.PolygonFilter(filename="CD66+_CD14-.poly")
mw.widget_quick_view.ui.pushButton_poly_create.click()
mw.widget_quick_view.ui.lineEdit_poly.setText("CD66⁺/CD14⁻")
mw.widget_quick_view.ui.widget_scatter.set_poly_points(pf.points)
# show an event
mw.widget_quick_view.ui.imageView_image_poly.show()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.widget_quick_view.grab().save("_ui_qv_poly.png")

# block matrix
mw.ui.block_matrix.setFixedSize(420, 320)
mw.ui.block_matrix.repaint()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.ui.block_matrix.ui.scrollArea_block.grab().save("_ui_block_matrix.png")

# analysis view
# add a dataset to the session that has tables, basins, more logs
mw.add_dataslot(paths=[here.parents[1] / "tests" / "data"
                       / "naiad-capture_blood_pipeline.rtdc"])

# Meta
mw.widget_ana_view.ui.tabWidget.setCurrentWidget(
    mw.widget_ana_view.ui.tab_meta)
mw.widget_ana_view.ui.widget_meta.ui.comboBox_slots.setCurrentIndex(2)
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.widget_ana_view.ui.widget_meta.repaint()
mw.widget_ana_view.grab().save("_ui_ana_meta.png")

# Basins
mw.widget_ana_view.ui.tabWidget.setCurrentWidget(
    mw.widget_ana_view.ui.tab_basins)
mw.widget_ana_view.ui.widget_basins.ui.listWidget_dataset.setCurrentRow(2)
item = mw.widget_ana_view.ui.widget_basins.treeWidget_basin_name.itemAt(0, 0)
mw.widget_ana_view.ui.widget_basins.treeWidget_basin_name.setCurrentItem(item)
mw.widget_ana_view.repaint()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.widget_ana_view.grab().save("_ui_ana_basins.png")

# Tables
mw.widget_ana_view.ui.tabWidget.setCurrentWidget(
    mw.widget_ana_view.ui.tab_tables)
mw.widget_ana_view.ui.widget_tables.ui.listWidget_dataset.setCurrentRow(2)
mw.widget_ana_view.ui.widget_tables.ui.listWidget_table_name.setCurrentRow(1)
for item in [
    mw.widget_ana_view.ui.widget_tables.ui.listWidget_table_graphs.item(0),
    mw.widget_ana_view.ui.widget_tables.ui.listWidget_table_graphs.item(2),
]:
    item.setSelected(True)
mw.widget_ana_view.repaint()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.widget_ana_view.grab().save("_ui_ana_tables.png")

# Logs
mw.widget_ana_view.ui.tabWidget.setCurrentWidget(
    mw.widget_ana_view.ui.tab_log)
mw.widget_ana_view.ui.widget_log.ui.listWidget_dataset.setCurrentRow(2)
mw.widget_ana_view.ui.widget_log.ui.listWidget_log_name.setCurrentRow(1)
mw.widget_ana_view.repaint()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.widget_ana_view.grab().save("_ui_ana_logs.png")

# Dataslot
mw.on_modify_slot(mw.pipeline.slot_ids[0])
mw.widget_ana_view.repaint()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.widget_ana_view.grab().save("_ui_ana_slot.png")

# Filter
mw.on_modify_filter(mw.pipeline.filter_ids[0])
mw.widget_ana_view.repaint()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.widget_ana_view.grab().save("_ui_ana_filter.png")

# Plots
mw.on_modify_plot(mw.pipeline.plot_ids[0])
mw.widget_ana_view.repaint()
QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
mw.widget_ana_view.grab().save("_ui_ana_plot.png")


mw.close()
