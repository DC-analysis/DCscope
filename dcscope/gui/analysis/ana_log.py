import importlib.resources

from pygments import highlight, lexers, formatters
from PyQt6 import uic, QtCore, QtWidgets


class LogPanel(QtWidgets.QWidget):
    """Log panel widget

    Visualizes logs stored in the .rtdc file
    """

    def __init__(self, *args, **kwargs):
        super(LogPanel, self).__init__(*args, **kwargs)
        ref = importlib.resources.files(
            "dcscope.gui.analysis") / "ana_log.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)
        # current DCscope pipeline
        self._pipeline = None
        self._selected_log = None
        self.listWidget_dataset.currentRowChanged.connect(
            self.on_select_dataset)
        self.listWidget_log_name.currentRowChanged.connect(
            self.on_select_log)
        self.update_content()

    @property
    def pipeline(self):
        return self._pipeline

    @QtCore.pyqtSlot(int)
    def on_select_dataset(self, ds_idx):
        """Show the logs of the dataset in the right-hand list widget"""
        self.listWidget_log_name.clear()
        if ds_idx >= 0:
            ds = self._pipeline.slots[ds_idx].get_dataset()
            log_names = list(ds.logs.keys())
            for log in log_names:
                self.listWidget_log_name.addItem(log)

            # Apply previously selected log
            if self._selected_log in log_names:
                log_idx = log_names.index(self._selected_log)
                self.listWidget_log_name.setCurrentRow(log_idx)
            elif len(log_names):
                self.listWidget_log_name.setCurrentRow(0)

    @QtCore.pyqtSlot(int)
    def on_select_log(self, log_index):
        """Show the logs of the dataset in the right-hand list widget"""
        ds_idx = self.listWidget_dataset.currentRow()
        if ds_idx >= 0:
            ds = self._pipeline.slots[ds_idx].get_dataset()
            if len(ds.logs) == 0:
                self.listWidget_log_name.clear()
                self.textEdit.clear()
                return

            if log_index >= len(ds.logs):
                self.on_select_log(0)
                return

            lines = ds.logs[list(ds.logs.keys())[log_index]]

            if lines[0].strip() == "{" and lines[-1].strip() == "}":
                # JSON
                text = highlight("\n".join(lines),
                                 lexers.JsonLexer(),
                                 formatters.HtmlFormatter(full=True,
                                                          noclasses=True,
                                                          nobackground=True))
            else:
                # Normal log
                linetypes = ["n"] * len(lines)
                for ii, line in enumerate(lines):
                    if line.count("ERROR"):
                        linetypes[ii] = "e"
                        # consecutive lines are also errors
                        for jj in range(ii+1, len(lines)):
                            if lines[jj].startswith("..."):
                                linetypes[jj] = "e"
                            else:
                                break
                    elif line.count("WARNING"):
                        linetypes[ii] = "w"
                        # consecutive lines are also errors
                        for jj in range(ii+1, len(lines)):
                            if lines[jj].startswith("..."):
                                linetypes[jj] = "w"
                            else:
                                break

                for ii, lt in enumerate(linetypes):
                    if lt == "e":
                        lines[ii] = \
                            f"<div style='color:#A60000'>{lines[ii]}</div>"
                    elif lt == "w":
                        lines[ii] = \
                            f"<div style='color:#7C4B00'>{lines[ii]}</div>"
                    else:
                        lines[ii] = f"<div>{lines[ii]}</div>"

                text = "\n".join(lines)

            self.textEdit.setText(text)
        else:
            self.listWidget_log_name.clear()
            self.textEdit.clear()

    def set_pipeline(self, pipeline):
        self._pipeline = pipeline

    def update_content(self, slot_index=None, **kwargs):
        if self._pipeline and self._pipeline.slots:
            self.setEnabled(True)
            self.setUpdatesEnabled(False)
            self.listWidget_dataset.clear()
            self.listWidget_log_name.clear()
            for slot in self._pipeline.slots:
                self.listWidget_dataset.addItem(slot.name)
            self.setUpdatesEnabled(True)
            if slot_index is None or slot_index < 0:
                slot_index = max(0, self.listWidget_dataset.currentRow())
            slot_index = min(slot_index, self._pipeline.num_slots - 1)
            self.listWidget_dataset.setCurrentRow(slot_index)
        else:
            self.setEnabled(False)
            self.listWidget_dataset.clear()
            self.listWidget_log_name.clear()
            self.textEdit.clear()
