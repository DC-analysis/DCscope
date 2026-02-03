import importlib.resources
import json

from pygments import highlight, lexers, formatters
from PyQt6 import uic, QtCore, QtWidgets


class BasinsPanel(QtWidgets.QWidget):
    """Tables panel widget

    Visualizes tables stored in the .rtdc file
    """
    # widgets emit these whenever they changed the pipeline
    pp_mod_send = QtCore.pyqtSignal(dict)
    # widgets receive these so they can reflect the pipeline changes
    pp_mod_recv = QtCore.pyqtSignal(dict)

    def __init__(self, *args, **kwargs):
        super(BasinsPanel, self).__init__(*args, **kwargs)
        ref = importlib.resources.files(
            "dcscope.gui.analysis") / "ana_basins.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)
        # current DCscope pipeline
        self.pipeline = None
        self.data_role = QtCore.Qt.ItemDataRole.UserRole + 2
        self.treeWidget_basin_name.setColumnCount(1)

        self.listWidget_dataset.currentRowChanged.connect(
            self.on_select_dataset)
        self.treeWidget_basin_name.currentItemChanged.connect(
            self.on_select_basin)

        self.pp_mod_recv.connect(self.on_pp_mod_recv)

    def add_basin_nodes(self, parent_widget, ds):
        for bd in ds.basins_get_dicts():
            # Get all basins
            item = QtWidgets.QTreeWidgetItem(parent_widget)
            item.setText(0, bd["name"])
            item.setData(0, self.data_role, (ds, bd))

    @QtCore.pyqtSlot(dict)
    def on_pp_mod_recv(self, data):
        """We received a signal that something changed"""
        if data.get("pipeline"):
            if self.isVisible():
                self.update_content()

    @QtCore.pyqtSlot(int)
    def on_select_dataset(self, ds_idx):
        """Show the tables of the dataset in the right-hand list widget"""
        self.treeWidget_basin_name.clear()
        if ds_idx >= 0:
            ds = self.pipeline.slots[ds_idx].get_dataset()
            self.add_basin_nodes(parent_widget=self.treeWidget_basin_name,
                                 ds=ds)

    @QtCore.pyqtSlot(QtWidgets.QTreeWidgetItem, QtWidgets.QTreeWidgetItem)
    def on_select_basin(self, current, previous=None):
        """Show the tables of the dataset in the right-hand list widget"""
        ds_idx = self.listWidget_dataset.currentRow()
        if current is not None and ds_idx >= 0:
            # Get the correct basin
            ds, bd = current.data(0, self.data_role)
            # try to access that basin in `ds`
            for bn in ds.basins:
                if bn.key == bd["key"]:
                    # We've got a match
                    loaded = True
                    available = bn.is_available()
                    break
            else:
                loaded = False
                available = False
                bn = None

            # Display the basin information
            self.label_status.setText(f"{loaded=}, {available=}")
            self.label_id.setText(f"{bd.get('name')} ({bd['key']})")
            self.textEdit_def.setText(
                highlight(json.dumps(bd, sort_keys=True, indent=2),
                          lexers.JsonLexer(),
                          formatters.HtmlFormatter(full=True,
                                                   noclasses=True,
                                                   nobackground=True))
            )

            if available and bn is not None and not current.childCount():
                # Add child tree nodes
                self.add_basin_nodes(parent_widget=current,
                                     ds=bn.ds)
                current.setExpanded(True)
        else:
            self.textEdit_def.clear()
            self.label_status.setText("")
            self.label_id.setText("")

    def set_pipeline(self, pipeline):
        if self.pipeline is not None:
            raise ValueError("Pipeline can only be set once")
        self.pipeline = pipeline

    def update_content(self, slot_index=None, **kwargs):
        if self.pipeline and self.pipeline.slots:
            self.setEnabled(True)
            self.setUpdatesEnabled(False)
            self.listWidget_dataset.clear()
            self.treeWidget_basin_name.clear()
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
            self.treeWidget_basin_name.clear()
