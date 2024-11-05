import importlib.resources

from PyQt6 import uic, QtCore, QtWidgets


class DlgSlotReorder(QtWidgets.QDialog):
    pipeline_changed = QtCore.pyqtSignal(dict)

    def __init__(self, pipeline, *args, **kwargs):
        super(DlgSlotReorder, self).__init__(*args, **kwargs)
        ref = importlib.resources.files(
            "shapeout2.gui.analysis") / "dlg_slot_reorder.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        self.pipeline = pipeline
        for ii, slot in enumerate(pipeline.slots):
            self.listWidget.addItem("{}: {}".format(ii, slot.name))

        self.toolButton_down.clicked.connect(self.on_move_item)
        self.toolButton_up.clicked.connect(self.on_move_item)
        btn_ok = self.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok)
        btn_ok.clicked.connect(self.on_ok)

    @QtCore.pyqtSlot()
    def on_ok(self):
        """Apply the changes made in the UI and update the pipeline"""
        # get order
        indices = []
        for row in range(self.listWidget.count()):
            item = self.listWidget.item(row)
            text = item.text()
            idx = int(text.split(":", 1)[0])
            indices.append(idx)
        # reorder pipeline and send pipeline_changed signal
        self.pipeline.reorder_slots(indices)
        state = self.pipeline.__getstate__()
        self.pipeline_changed.emit(state)

    @QtCore.pyqtSlot()
    def on_move_item(self):
        """Move currently selected item one row up or down"""
        row = self.listWidget.currentRow()
        if row == -1:
            return
        item = self.listWidget.takeItem(row)

        if self.sender() == self.toolButton_down:
            new_row = row + 1
        else:
            new_row = row - 1

        self.listWidget.insertItem(new_row, item)
        self.listWidget.setCurrentRow(new_row)
