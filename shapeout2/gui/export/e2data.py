import pathlib
import importlib.resources

from PyQt6 import uic, QtCore, QtWidgets

import dclab

from ..widgets import get_directory, show_wait_cursor
from ..widgets.feature_combobox import HIDDEN_FEATURES

from ...util import get_valid_filename
from ..._version import version


class ExportData(QtWidgets.QDialog):
    def __init__(self, parent, pipeline, *args, **kwargs):
        super(ExportData, self).__init__(parent=parent, *args, **kwargs)
        ref = importlib.resources.files("shapeout2.gui.export") / "e2data.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        # output path
        self._path = None
        # Get output path
        self.on_browse(force_dialog=False)
        # set pipeline
        self.pipeline = pipeline
        # update list widget
        self.bulklist_features.set_title("Features")
        self.on_radio()
        self.on_select_features_innate()
        # Set storage strategy options
        self.comboBox_storage.clear()
        self.comboBox_storage.addItem(
            "No basins: Store only selected features (legacy behavior)",
            "no-basins"
        )
        self.comboBox_storage.addItem(
            "With basins: Store features, link to original data (recommended)",
            "with-basins"
        )
        self.comboBox_storage.addItem(
            "Only basins: Do not store features, link to original data (fast)",
            "only-basins"
        )
        self.comboBox_storage.setCurrentIndex(
            self.comboBox_storage.findData("with-basins"))
        # Signals
        self.pushButton_path.clicked.connect(self.on_browse)
        # file type selection
        self.radioButton_fcs.clicked.connect(self.on_radio)
        self.radioButton_rtdc.clicked.connect(self.on_radio)
        self.radioButton_tsv.clicked.connect(self.on_radio)
        # storage strategy selection
        self.comboBox_storage.currentIndexChanged.connect(
            self.on_storage_strategy)

    @property
    def file_format(self):
        if self.radioButton_fcs.isChecked():
            return "fcs"
        elif self.radioButton_rtdc.isChecked():
            return "rtdc"
        else:
            return "tsv"

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, value):
        if value and pathlib.Path(value).exists():
            self._path = value
            self.lineEdit_path.setText(value)

    @property
    def storage_strategy(self):
        if self.file_format == "rtdc":
            storage_strategy = self.comboBox_storage.currentData()
        else:
            storage_strategy = "no-basins"
        return storage_strategy

    def done(self, r):
        if r:
            self.export_data()
        super(ExportData, self).done(r)

    @show_wait_cursor
    @QtCore.pyqtSlot()
    def export_data(self):
        """Export data to the desired file format"""
        # get features
        if self.storage_strategy == "only-basins":
            # This case will also only happen for the .rtdc format
            features = []
        else:
            features = self.bulklist_features.get_selection()
        pend = len(self.pipeline.slots)
        prog = QtWidgets.QProgressDialog("Exporting...", "Abort", 1,
                                         pend, self)
        prog.setWindowTitle("Data Export")
        prog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        prog.setMinimumDuration(0)
        prog.setValue(0)
        QtWidgets.QApplication.processEvents(
            QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)

        slots_n_paths = self.get_export_filenames()
        prog.setMaximum(len(slots_n_paths))  # correct dialog maximum

        for slot_index, path in slots_n_paths:
            ds = self.pipeline.get_dataset(slot_index)
            # check features
            fmiss = [ff for ff in features if ff not in ds.features]
            if fmiss:
                lmiss = [dclab.dfn.get_feature_label(ff) for ff in fmiss]
                QtWidgets.QMessageBox.warning(
                    self,
                    "Features missing!",
                    (f"Dataslot {slot_index} does not have these features:"
                     + "\n"
                     + "".join([f"\n- {fl}" for fl in lmiss])
                     + "\n\n"
                     + f"They are not exported to .{self.file_format}!")
                )
            if self.file_format == "rtdc":
                ds.export.hdf5(
                    path=path,
                    features=[ff for ff in features if ff in ds.features],
                    logs=True,
                    tables=True,
                    basins=self.storage_strategy != "no-basins",
                    meta_prefix="",
                    override=False)
            elif self.file_format == "fcs":
                ds.export.fcs(
                    path=path,
                    features=[ff for ff in features if ff in ds.features],
                    meta_data={"Shape-Out version": version},
                    override=False)
            else:
                ds.export.tsv(
                    path=path,
                    features=[ff for ff in features if ff in ds.features],
                    meta_data={"Shape-Out version": version},
                    override=False)
            if prog.wasCanceled():
                break
            prog.setValue(slot_index + 1)
            QtWidgets.QApplication.processEvents(
                QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
        prog.setValue(pend)

    def get_export_filenames(self):
        """Compute names for exporting data, avoiding overriding anything

        Return a list of tuples `(slot_index, filename)`.
        """
        # for every slot there is a path
        slots_n_paths = []
        out = pathlib.Path(self.path)
        # assemble the slots
        slots = []
        for s_index in range(len(self.pipeline.slots)):
            slot = self.pipeline.slots[s_index]
            if slot.slot_used:
                slots.append((s_index, slot))
        # find non-existent file names
        ap = ""  # this gets appended to the file stem if the file exists
        counter = 0  # counts up an index for appending to the file
        while True:
            slots_n_paths.clear()
            for s_index, slot in slots:
                fn = f"SO2-export_{s_index}_{slot.name}{ap}.{self.file_format}"
                # remove bad characters from file name
                fn = get_valid_filename(fn)
                path = out / fn
                if path.exists():
                    # The file already exists. Break here and the counter
                    # is incremented for a next iteration.
                    break
                else:
                    # Everything good so far.
                    slots_n_paths.append((s_index, path))
            else:
                # If nothing in the for loop caused it to break, then we
                # have a fully populated list of slots_n_paths, and we can
                # exit this while-loop.
                break

            counter += 1
            ap = f"_{counter}"
        # Return the list of slots and corresponding paths
        return slots_n_paths

    @QtCore.pyqtSlot()
    def on_browse(self, force_dialog=True):
        self.path = get_directory(
            parent=self,
            identifier="export data",
            caption="Export directory",
            force_dialog=force_dialog
        )

    @QtCore.pyqtSlot()
    def on_radio(self):
        self.update_feature_list()
        self.widget_storage_strategy.setEnabled(self.file_format == "rtdc")
        # set storage strategy based on file format
        strategy = "with-basins" if self.file_format == "rtdc" else "no-basins"
        self.comboBox_storage.setCurrentIndex(
            self.comboBox_storage.findData(strategy))

    @QtCore.pyqtSlot()
    def on_select_features_innate(self):
        """Only select all innate features of the first dataset"""
        if self.pipeline.num_slots:
            ds = self.pipeline.get_dataset(0)
            features_loaded = ds.features_loaded
            lw = self.bulklist_features.listWidget
            for ii in range(lw.count()):
                wid = lw.item(ii)
                for feat in features_loaded:
                    if wid.data(101) == feat:
                        wid.setCheckState(QtCore.Qt.CheckState.Checked)
                        break
                else:
                    wid.setCheckState(QtCore.Qt.CheckState.Unchecked)

    @QtCore.pyqtSlot()
    def on_storage_strategy(self):
        self.bulklist_features.setEnabled(
            self.storage_strategy != "only-basins")

    def update_feature_list(self, scalar=False):
        if self.file_format == "rtdc":
            self.features = self.pipeline.get_features(union=True,
                                                       label_sort=True)
            # do not allow exporting event index, since it will be
            # re-enumerated in any case.
            self.features.remove("index")
        else:
            self.features = self.pipeline.get_features(scalar=True,
                                                       union=True,
                                                       label_sort=True)
        # do not export basinmap features
        for feat in HIDDEN_FEATURES + ["index"]:
            if feat in self.features:
                self.features.remove(feat)

        labels = [dclab.dfn.get_feature_label(feat) for feat in self.features]
        self.bulklist_features.set_items(self.features, labels)
        self.on_select_features_innate()
