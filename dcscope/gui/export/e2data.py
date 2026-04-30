import logging
import pathlib
import traceback

from PyQt6 import QtCore, QtTest, QtWidgets

import dclab

from ...util import get_valid_filename
from ..._version import version
from ..widgets import get_directory, show_wait_cursor
from ..widgets.feature_combobox import HIDDEN_FEATURES
from .e2data_ui import Ui_Dialog

logger = logging.getLogger(__name__)


class ExportData(QtWidgets.QDialog):
    def __init__(self, parent, pipeline, *args, **kwargs):
        super(ExportData, self).__init__(parent=parent, *args, **kwargs)

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.features = []

        # output path
        self._path = None
        # Get output path
        self.on_browse(force_dialog=False)
        # set pipeline
        self.pipeline = pipeline
        # update list widget
        self.ui.bulklist_features.set_title("Features")
        self.on_radio()
        self.on_select_features_innate()
        # Set storage strategy options
        self.ui.comboBox_storage.clear()
        self.ui.comboBox_storage.addItem(
            "No basins: Store only selected features (legacy behavior)",
            "no-basins"
        )
        self.ui.comboBox_storage.addItem(
            "With basins: Store features, link to original data (recommended)",
            "with-basins"
        )
        self.ui.comboBox_storage.addItem(
            "Only basins: Do not store features, link to original data (fast)",
            "only-basins"
        )
        self.ui.comboBox_storage.setCurrentIndex(
            self.ui.comboBox_storage.findData("with-basins"))
        # Signals
        self.ui.pushButton_path.clicked.connect(self.on_browse)
        # file type selection
        self.ui.radioButton_fcs.clicked.connect(self.on_radio)
        self.ui.radioButton_rtdc.clicked.connect(self.on_radio)
        self.ui.radioButton_tsv.clicked.connect(self.on_radio)
        self.ui.radioButton_avi.clicked.connect(self.on_radio)
        # storage strategy selection
        self.ui.comboBox_storage.currentIndexChanged.connect(
            self.on_storage_strategy)

        self.ui.comboBox_format.clear()
        self.ui.comboBox_format.addItem("MKV", "mkv")
        self.ui.comboBox_format.addItem("AVI", "avi")
        self.ui.comboBox_format.addItem("MOV", "mov")

        self.ui.comboBox_codec.clear()
        self.ui.comboBox_codec.addItem(
            "H264 (high quality, fast export)",
            {"pixel_format": "yuv420p",
             "codec": "libx264",
             "codec_options": {'preset': 'ultrafast',
                               'crf': '0'}})
        self.ui.comboBox_codec.addItem(
            "H264 (high quality, small file size)",
            {"pixel_format": "yuv420p",
             "codec": "libx264",
             "codec_options": {'preset': 'slow',
                               'crf': '0'}})
        self.ui.comboBox_codec.addItem(
            "H264 (lossy compression)",
            {"pixel_format": "yuv420p",
             "codec": "libx264",
             "codec_options": {'preset': 'slow',
                               'crf': '7'}})
        self.ui.comboBox_codec.addItem(
            "RAW (huge files)",
            {"pixel_format": "yuv420p",
             "codec": "rawvideo"})

    @property
    def file_format(self):
        if self.ui.radioButton_fcs.isChecked():
            return "fcs"
        elif self.ui.radioButton_rtdc.isChecked():
            return "rtdc"
        elif self.ui.radioButton_avi.isChecked():
            return self.ui.comboBox_format.currentData()
        else:
            return "tsv"

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, value):
        if value and pathlib.Path(value).exists():
            self._path = value
            self.ui.lineEdit_path.setText(value)

    @property
    def storage_strategy(self):
        if self.file_format == "rtdc":
            storage_strategy = self.ui.comboBox_storage.currentData()
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
        elif self.ui.radioButton_avi.isChecked():
            # We are only exporting images
            features = []
        else:
            features = self.ui.bulklist_features.get_selection()

        # create dummy progress dialog
        prog = QtWidgets.QProgressDialog("Exporting...", "Abort", 1,
                                         10, self)
        prog.setWindowTitle("Data Export")
        prog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        prog.setMinimumDuration(0)
        prog.setAutoClose(True)
        QtWidgets.QApplication.processEvents(
            QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)

        # correct dialog maximum
        prog.setValue(0)
        slots_n_paths = self.get_export_filenames()
        pend = len(slots_n_paths) * 100
        prog.setMaximum(pend)
        QtWidgets.QApplication.processEvents(
            QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)

        tasks = []

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
                tasks.append((
                    ds.export.hdf5,
                    dict(path=path,
                         features=[ff for ff in features if ff in ds.features],
                         logs=True,
                         tables=True,
                         basins=self.storage_strategy != "no-basins",
                         meta_prefix="",
                         override=False)
                ))
            elif self.file_format == "fcs":
                tasks.append((
                    ds.export.fcs,
                    dict(path=path,
                         features=[ff for ff in features if ff in ds.features],
                         meta_data={"DCscope version": version},
                         override=False)
                ))
            elif self.file_format == "tsv":
                tasks.append((
                    ds.export.tsv,
                    dict(path=path,
                         features=[ff for ff in features if ff in ds.features],
                         meta_data={"DCscope version": version},
                         override=False)
                ))
            elif self.ui.radioButton_avi.isChecked():
                tasks.append((
                    ds.export.avi,
                    dict(path=path,
                         **self.ui.comboBox_codec.currentData())
                ))

        logger.info(f"Exporting {len(tasks)} objects")

        exporter = ExportThread(self, tasks)
        exporter.communicate_progress.connect(prog.setValue)
        exporter.communicate_message.connect(prog.setLabelText)
        prog.canceled.connect(exporter.request_abort)
        exporter.start()

        while True:
            QtWidgets.QApplication.processEvents(
                QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
            QtTest.QTest.qWait(500)
            if prog.wasCanceled() or exporter.isFinished():
                # This will break the loop but possibly keep the exporter
                # alive. We hope that the exporter will eventually be
                # terminated.
                break

        prog.setValue(pend)

        if prog.wasCanceled():
            exporter.terminate()
        else:
            exporter.wait()

        if exporter.failed_tasks:
            info_string = "\n".join(
                [f"- {kw['path']}" for _, kw in exporter.failed_tasks])
            QtWidgets.QMessageBox.critical(
                self, f"Error exporting {len(exporter.failed_tasks)} objects",
                f"Could not export to the following paths:\n{info_string}")

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
        self.ui.widget_storage_strategy.setEnabled(self.file_format == "rtdc")
        # set storage strategy based on file format
        strategy = "with-basins" if self.file_format == "rtdc" else "no-basins"
        self.ui.comboBox_storage.setCurrentIndex(
            self.ui.comboBox_storage.findData(strategy))

        if self.ui.radioButton_avi.isChecked():
            self.ui.stackedWidget.setCurrentWidget(self.ui.page_video)
        else:
            self.update_feature_list()
            self.ui.stackedWidget.setCurrentWidget(self.ui.page_features)

    @QtCore.pyqtSlot()
    def on_select_features_innate(self):
        """Only select all innate features of the first dataset"""
        if self.pipeline.num_slots:
            ds = self.pipeline.get_dataset(0)
            features_loaded = ds.features_loaded
            lw = self.ui.bulklist_features.ui.listWidget
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
        self.ui.bulklist_features.setEnabled(
            self.storage_strategy != "only-basins")

    def update_feature_list(self, scalar=False):
        if self.file_format == "rtdc":
            self.features = self.pipeline.get_features(union=True,
                                                       label_sort=True)
            # do not allow exporting event index, since it will be
            # re-enumerated in any case.
            self.features.remove("index")
            # do not allow exporting contour data, since that is covered
            # by "mask" and takes ages to write/read.
            if "contour" in self.features:
                self.features.remove("contour")
        else:
            self.features = self.pipeline.get_features(scalar=True,
                                                       union=True,
                                                       label_sort=True)
        # do not export basinmap features
        for feat in HIDDEN_FEATURES + ["index"]:
            if feat in self.features:
                self.features.remove(feat)

        labels = [dclab.dfn.get_feature_label(feat) for feat in self.features]
        self.ui.bulklist_features.set_items(self.features, labels)
        self.on_select_features_innate()


class ExportAbortError(BaseException):
    """Used for aborting data export via progress_callback"""
    pass


class ExportThread(QtCore.QThread):
    communicate_progress = QtCore.pyqtSignal(int)
    communicate_message = QtCore.pyqtSignal(str)

    def __init__(self, parent, tasks):
        super(ExportThread, self).__init__(parent)
        self.abort = False
        self.tasks = tasks
        self.current_path = None
        self.tasks_done = []
        self.failed_tasks = []
        self.setObjectName(self.__class__.__name__)

    def progress_callback(self, progress, message):
        cur_pos = int((len(self.tasks_done) + progress) * 100)
        self.communicate_progress.emit(cur_pos)
        self.communicate_message.emit(f"{self.current_path.name} ({message})")
        if self.abort:
            raise ExportAbortError("User aborted")

    def run(self):
        for ii in range(len(self.tasks)):
            if self.abort:
                break
            func, kwargs = self.tasks.pop(0)
            self.current_path = pathlib.Path(kwargs["path"])
            try:
                func(progress_callback=self.progress_callback, **kwargs)
            except ExportAbortError:
                # remove current path
                self.current_path.unlink(missing_ok=True)
                break
            except BaseException:
                # remove current path
                self.current_path.unlink(missing_ok=True)
                logger.error(traceback.format_exc())
                self.failed_tasks.append((func, kwargs))
                continue
            finally:
                self.tasks_done.append((func, kwargs))

    @QtCore.pyqtSlot()
    def request_abort(self):
        self.abort = True
