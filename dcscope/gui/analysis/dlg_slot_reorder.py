from PyQt6 import QtCore, QtWidgets

from .dlg_slot_reorder_ui import Ui_Dialog


class DlgSlotReorder(QtWidgets.QDialog):
    pp_mod_send = QtCore.pyqtSignal(dict)

    def __init__(self, pipeline, *args, **kwargs):
        super(DlgSlotReorder, self).__init__(*args, **kwargs)

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.pipeline = pipeline
        for ii, slot in enumerate(pipeline.slots):
            self.ui.listWidget.addItem("{}: {}".format(ii, slot.name))

        self.ui.toolButton_down.clicked.connect(self.on_move_item)
        self.ui.toolButton_up.clicked.connect(self.on_move_item)
        btn_ok = self.ui.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok)
        btn_ok.clicked.connect(self.on_ok)

    @QtCore.pyqtSlot()
    def on_ok(self):
        """Apply the changes made in the UI and update the pipeline"""
        # get order
        indices = []
        for row in range(self.ui.listWidget.count()):
            item = self.ui.listWidget.item(row)
            text = item.text()
            idx = int(text.split(":", 1)[0])
            indices.append(idx)
        # reorder pipeline and send pipeline_changed signal
        with self.pipeline.lock:
            self.pipeline.reorder_slots(indices)
        self.pp_mod_send.emit({"pipeline": {"slot_order_changed": indices}})

    @QtCore.pyqtSlot()
    def on_move_item(self):
        """Move currently selected item one row up or down"""
        row = self.ui.listWidget.currentRow()
        if row == -1:
            return
        item = self.ui.listWidget.takeItem(row)

        if self.sender() == self.ui.toolButton_down:
            new_row = row + 1
        else:
            new_row = row - 1

        self.ui.listWidget.insertItem(new_row, item)
        self.ui.listWidget.setCurrentRow(new_row)
