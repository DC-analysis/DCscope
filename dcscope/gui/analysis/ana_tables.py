import importlib.resources
import io

import numpy as np
import pyqtgraph as pg
from PyQt6 import uic, QtCore, QtGui, QtWidgets

#: Fallback graph colors
FALLBACK_COLORS = {
    'brightness': '#d8d000',
    'cpu_cs': '#b41010',
    'cpu_sys': '#8e0505',
    'disk': '#949494',
    'flow_rate_sample': '#00049C',
    'flow_rate_sheath': '#00049C',
    'focus': '#a03000',
    'imaging_rate': '#6b02e8',
    'pressure_sample': '#7c7c7c',
    'pressure_sheath': '#6c6c6c',
    'ram_cam': '#db8400',
    'ram_wrt': '#bf770a',
    'recording_rate': '#4858e8',
    'rotation': '#6ecf0d',
    'shift': '#0e8f69',
    'temperature_camera': '#8005b8',
    'temperature_chip': '#b80589',
    'time': '#000000'
}


def get_foreground_for_background(color):
    """Given background color, yield black or white"""
    color = QtGui.QColor(color)
    color_mean = np.mean([color.red(), color.blue(), color.green()])
    if color_mean < 255 / 2:
        return "white"
    else:
        return "black"


class TablesPanel(QtWidgets.QWidget):
    """Tables panel widget

    Visualize tables stored in the .rtdc file
    """
    # widgets emit these whenever they changed the pipeline
    pp_mod_send = QtCore.pyqtSignal(dict)
    # widgets receive these so they can reflect the pipeline changes
    pp_mod_recv = QtCore.pyqtSignal(dict)

    def __init__(self, *args, **kwargs):
        super(TablesPanel, self).__init__(*args, **kwargs)
        ref = importlib.resources.files(
            "dcscope.gui.analysis") / "ana_tables.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)
        # current DCscope pipeline
        self.pipeline = None
        self._selected_table = None
        self._selected_graphs = []

        self.legend = pg.LegendItem((80, 60),
                                    offset=(40, 20))
        self.legend.setParentItem(self.graphicsView_lines.graphicsItem())
        self.graphicsView_lines.showGrid(True, True)
        self.tabWidget.setCurrentIndex(0)

        self.listWidget_dataset.currentRowChanged.connect(
            self.on_select_dataset)
        self.listWidget_table_name.currentRowChanged.connect(
            self.on_select_table)
        self.listWidget_table_graphs.itemSelectionChanged.connect(
            self.on_select_graphs)

        self.pp_mod_recv.connect(self.on_pp_mod_recv)

    @QtCore.pyqtSlot(dict)
    def on_pp_mod_recv(self, data):
        """We received a signal that something changed"""
        if data.get("pipeline"):
            if self.isVisible():
                self.update_content()

    @QtCore.pyqtSlot(int)
    def on_select_dataset(self, ds_idx):
        """Show the tables of the dataset in the right-hand list widget"""
        self.listWidget_table_name.clear()
        self.listWidget_table_graphs.clear()
        if ds_idx >= 0:
            ds = self.pipeline.slots[ds_idx].get_dataset()
            table_names = list(ds.tables.keys())
            self.listWidget_table_name.blockSignals(True)
            for table in table_names:
                self.listWidget_table_name.addItem(table)
            self.listWidget_table_name.blockSignals(False)

            # Apply previously selected tables
            if self._selected_table in table_names:
                table_idx = table_names.index(self._selected_table)
                self.listWidget_table_name.setCurrentRow(table_idx)
            elif len(table_names):
                self.listWidget_table_name.setCurrentRow(0)

    @QtCore.pyqtSlot(int)
    def on_select_table(self, table_index):
        """Show the tables of the dataset in the right-hand list widget"""
        ds_idx = self.listWidget_dataset.currentRow()
        if ds_idx >= 0 and table_index >= 0:
            ds = self.pipeline.slots[ds_idx].get_dataset()
            self._selected_table = list(ds.tables.keys())[table_index]
            table = ds.tables[self._selected_table]
            names = table[:].dtype.names

            if names is not None:
                # We have a rec-array, a list of graphs in the table
                self.listWidget_table_graphs.setEnabled(True)
                self.stackedWidget_plot.setCurrentWidget(self.page_graph)
                # Update list of graphs names
                self.listWidget_table_graphs.blockSignals(True)
                self.listWidget_table_graphs.clear()
                for ii, graph in enumerate(names):
                    self.listWidget_table_graphs.addItem(graph)
                    color = table.meta.get(f"COLOR_{graph}",
                                           FALLBACK_COLORS.get(graph,
                                                               "black")
                                           )
                    self.listWidget_table_graphs.item(ii).setBackground(
                        QtGui.QColor(color))
                    self.listWidget_table_graphs.item(ii).setForeground(
                        QtGui.QColor(get_foreground_for_background(color)))

                # Apply previously selected graphs
                for graph in names:
                    if graph in list(self._selected_graphs):
                        graph_index = names.index(graph)
                        item = self.listWidget_table_graphs.item(graph_index)
                        if item:
                            item.setSelected(True)
                self.listWidget_table_graphs.blockSignals(False)
                self.on_select_graphs()
            else:
                self.listWidget_table_graphs.setEnabled(False)
                self.listWidget_table_graphs.clear()
                self.stackedWidget_plot.setCurrentWidget(self.page_image)
                self.graphicsView_image.setImage(table[:])
        else:
            self.listWidget_table_graphs.setEnabled(False)
            self.listWidget_table_name.clear()
            self.listWidget_table_graphs.clear()

    @QtCore.pyqtSlot()
    def on_select_graphs(self):
        """Show the graphs of one table of a dataset"""
        ds_idx = self.listWidget_dataset.currentRow()
        table_index = self.listWidget_table_name.currentRow()
        if ds_idx >= 0 and table_index >= 0:
            items = self.listWidget_table_graphs.selectedIndexes()
            new_selection = [it.data() for it in items]
            if new_selection:
                self._selected_graphs = new_selection
            ds = self.pipeline.slots[ds_idx].get_dataset()
            table = ds.tables[list(ds.tables.keys())[table_index]]
            table_data = table[:]
            names = table_data.dtype.names
            if table.has_graphs():
                # assemble the graph list
                graph_list = []
                if "time" in names:
                    x_vals = {"name": "time",
                              "data": table_data["time"].flatten()}
                else:
                    x_vals = {"name": "index",
                              "data": np.arange(len(table_data))}

                for graph in new_selection:
                    graph_list.append({
                        "name": graph,
                        "data": table_data[graph].flatten(),
                        "color": table.meta.get(f"COLOR_{graph}",
                                                FALLBACK_COLORS.get(graph,
                                                                    "black")
                                                )
                    })
                if new_selection:
                    # show the graph
                    self.show_graph(x_vals, graph_list)
                    self.show_raw_data(graph_list)
                    self.graphicsView_lines.autoRange()
                else:
                    self.graphicsView_lines.clear()
        else:
            self.listWidget_table_graphs.clear()

    def set_pipeline(self, pipeline):
        if self.pipeline is not None:
            raise ValueError("Pipeline can only be set once")
        self.pipeline = pipeline

    def show_graph(self, x_vals, graph_list):
        self.graphicsView_lines.clear()
        self.legend.clear()
        for item in graph_list:
            pl = self.graphicsView_lines.plot(
                pen={"color": item["color"],
                     "width": 2},
                x=x_vals["data"],
                y=item["data"],
                name=item["name"],
            )

            self.legend.addItem(pl, item["name"])
        self.graphicsView_lines.plotItem.setLabels(bottom=x_vals["name"])

    def show_raw_data(self, graph_list):
        text = "\t".join(it["name"] for it in graph_list)
        # save the array into a temporary string
        s = io.StringIO()
        data = np.array([it["data"] for it in graph_list]).transpose()
        np.savetxt(s, data, delimiter="\t", fmt="%.5g", header=text)
        self.plainTextEdit_raw.setPlainText(s.getvalue())

    def update_content(self, slot_index=None, **kwargs):
        if self.pipeline and self.pipeline.slots:
            self.setEnabled(True)
            self.setUpdatesEnabled(False)
            self.listWidget_dataset.clear()
            self.listWidget_table_name.clear()
            for slot in self.pipeline.slots:
                self.listWidget_dataset.addItem(slot.name)
            self.setUpdatesEnabled(True)
            if slot_index is None or slot_index < 0:
                slot_index = max(0, self.listWidget_dataset.currentRow())
            slot_index = min(slot_index, self.pipeline.num_slots - 1)
            self.listWidget_dataset.setCurrentRow(slot_index)
        else:
            self.setEnabled(False)
            self.listWidget_dataset.clear()
            self.listWidget_table_name.clear()
