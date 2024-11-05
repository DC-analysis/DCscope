import importlib.resources

from PyQt6 import uic, QtCore, QtWidgets


class BulkList(QtWidgets.QWidget):

    def __init__(self, parent, title=None, items=None, *args, **kwargs):
        """A checkable list with bulk (de-)selection button"""
        super(BulkList, self).__init__(parent=parent, *args, **kwargs)
        ref = importlib.resources.files(
            "shapeout2.gui.widgets") / "bulk_list.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        if title is not None:
            self.set_title(title)

        if items is not None:
            self.set_items(items)

        # select none by default
        self.on_select_none()

        # signals
        self.toolButton_all.clicked.connect(self.on_select_all)
        self.toolButton_none.clicked.connect(self.on_select_none)

    def get_selection(self):
        items = []
        for ii in range(self.listWidget.count()):
            wid = self.listWidget.item(ii)
            if wid.checkState() == QtCore.Qt.CheckState.Checked:
                items.append(wid.data(101))
        return items

    def set_items(self, items, labels=None):
        """Set the items of the list widget

        Parameters
        ----------
        items: list
            A list of the items in the list. If `labels` is
            None then this must be a list of strings. This
            is what is returned by `get_selection`.
        labels: list of str
            If set, use these strings as placeholders in the
            list widget.
        """
        if labels is None:
            labels = items
        self.listWidget.clear()
        for item, label in zip(items, labels):
            wid = QtWidgets.QListWidgetItem(label)
            wid.setData(101, item)
            wid.setCheckState(QtCore.Qt.CheckState.Unchecked)
            self.listWidget.addItem(wid)

    def set_title(self, title):
        """Set the title of the group box"""
        self.groupBox.setTitle(title)

    @QtCore.pyqtSlot()
    def on_select_all(self):
        """Select all items"""
        self.toolButton_none.setVisible(True)
        self.toolButton_all.setVisible(False)
        for ii in range(self.listWidget.count()):
            wid = self.listWidget.item(ii)
            wid.setCheckState(QtCore.Qt.CheckState.Checked)

    @QtCore.pyqtSlot()
    def on_select_none(self):
        """Deselect all items"""
        self.toolButton_none.setVisible(False)
        self.toolButton_all.setVisible(True)
        for ii in range(self.listWidget.count()):
            wid = self.listWidget.item(ii)
            wid.setCheckState(QtCore.Qt.CheckState.Unchecked)
