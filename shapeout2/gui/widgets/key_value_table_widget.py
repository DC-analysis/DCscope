import pathlib
import importlib.resources

import numpy as np
from PyQt6 import QtCore, QtWidgets


class KeyValueTableWidget(QtWidgets.QTableWidget):
    def __init__(self, *args, **kwargs):
        """A table widgets with two columns for key-value visualization"""
        super(KeyValueTableWidget, self).__init__(*args, **kwargs)
        ref = importlib.resources.files(
            "shapeout2.gui.widgets") / "key_value_table_widget.css"
        with importlib.resources.as_file(ref) as path_css:
            stylesheet = pathlib.Path(path_css).read_text()
        self.setStyleSheet(stylesheet)
        self.horizontalHeader().hide()
        self.verticalHeader().hide()
        self.setAlternatingRowColors(True)
        self.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        # For some reason this does not work here.
        # self.setColumnCount(2)
        # header = self.horizontalHeader()
        # header.setSectionResizeMode(0,
        #                             QtWidgets.QHeaderView.ResizeToContents)
        # header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)

    def set_key_vals(self, keys, vals, max_key_len=23):
        """Convenience function for setting key-value pairs in this table"""
        # disable updates
        self.setUpdatesEnabled(False)
        # rows'n'cols
        self.setRowCount(len(keys))
        self.setColumnCount(2)
        # populate
        for ii, (hi, vi) in enumerate(zip(keys, vals)):
            # name
            if len(hi) < max_key_len:
                name_vis = hi
            else:
                name_vis = hi[:max_key_len-3] + "..."
            # pad with spaces (b/c css padding caused overlap)
            name_vis = " " + name_vis + " "
            label_name = self.item(ii, 0)
            if label_name is None:
                label_name = QtWidgets.QTableWidgetItem(name_vis)
                label_name.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                self.setItem(ii, 0, label_name)
            else:
                if label_name.text() != name_vis:
                    label_name.setText(name_vis)
            label_name.setToolTip(hi)
            # value
            if np.isnan(vi) or np.isinf(vi):
                fmt = "{}"
            else:
                fmt = "{:.7g}"
            value_vis = fmt.format(vi)
            label_value = self.item(ii, 1)
            if label_value is None:
                label_value = QtWidgets.QTableWidgetItem(value_vis)
                label_value.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                self.setItem(ii, 1, label_value)
            else:
                label_value.setText(value_vis)
            label_value.setToolTip(hi)
        # spacing (did not work in __init__)
        header = self.horizontalHeader()
        header.setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1,
                                    QtWidgets.QHeaderView.ResizeMode.Stretch)
        # enable updates again
        self.setUpdatesEnabled(True)
