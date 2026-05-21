import logging
import pathlib
import threading
import traceback
from typing import Callable

from PyQt6 import QtCore, QtTest, QtWidgets

import dclab

from ...util import get_valid_filename
from ..._version import version
from ..tasks import TaskManager, TaskAbortError
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

    def done(self, a0):
        if a0:
            self.export_data()
        super(ExportData, self).done(a0)

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

        tm = TaskManager(self)

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

        jobs = []

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
                jobs.append((
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
                jobs.append((
                    ds.export.fcs,
                    dict(path=path,
                         features=[ff for ff in features if ff in ds.features],
                         meta_data={"DCscope version": version},
                         override=False)
                ))
            elif self.file_format == "tsv":
                jobs.append((
                    ds.export.tsv,
                    dict(path=path,
                         features=[ff for ff in features if ff in ds.features],
                         meta_data={"DCscope version": version},
                         override=False)
                ))
            elif self.ui.radioButton_avi.isChecked():
                jobs.append((
                    ds.export.avi,
                    dict(path=path,
                         **self.ui.comboBox_codec.currentData())
                ))

        logger.info(f"Exporting {len(jobs)} objects")

        task = {"func": perform_export,
                "args": [],
                "kwargs": {"jobs": jobs}
                }
        tm.add_task(
            task=task,
            topic="export",
            communicate_progress=prog.setValue,
            communicate_message=prog.setLabelText,
        )

        while True:
            QtTest.QTest.qWait(500)
            if prog.wasCanceled():
                tm.abort_task(task)
                while tm.is_task_running(task):
                    # force user to wait until the task properly aborted
                    prog.show()
                    prog.setLabelText("Aborting, please wait...")
                    prog.setMaximum(0)
                    prog.setMinimum(0)
                    QtTest.QTest.qWait(500)
                break
            elif tm.is_task_finished(task):
                result = tm.get_task_result(task)
                if result["jobs_failed"]:
                    info_string = "\n".join(
                        [f"- {kw['path']}" for _, kw in result["jobs_failed"]])
                    QtWidgets.QMessageBox.critical(
                        self,
                        f"Error exporting {len(result['jobs_failed'])} "
                        f"datasets",
                        f"Could not export to the following "
                        f"paths:\n{info_string}")
                break

        prog.deleteLater()
        tm.close()

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


def perform_export(jobs: list[tuple[Callable, dict]],
                   communicate_progress: Callable,
                   communicate_message: Callable,
                   event_abort: threading.Event
                   ) -> dict[str, list[tuple[Callable, dict]]]:
    """Perform data export

    Parameters
    ----------
    jobs:
        list of job dictionaries. Each job consists of a callable and the
        corresponding keyword arguments.
    communicate_progress:
        method for communicating the overall progress
        (used for progress bar)
    communicate_message:
        method for communicating the current progress message
        (used for progress bar)
    event_abort:
        an event that can be set to abort the export

    Returns
    -------
    result:
        dictionary with "jobs_done" and "jobs_failed" lists
    """
    jobs_failed = []
    jobs_done = []

    def handle_export_progress(idx, progress, message):
        communicate_progress(int((idx + progress)*100))
        communicate_message(message)

    for ii in range(len(jobs)):
        if event_abort.is_set():
            break
        func, kwargs = jobs.pop(0)
        current_path = pathlib.Path(kwargs["path"])
        try:
            func(progress_callback=lambda p, m: (
                    handle_export_progress(ii, p, m)),
                 **kwargs)
        except TaskAbortError:
            # cleanup: remove current path
            current_path.unlink(missing_ok=True)
            raise
        except BaseException:
            # remove current path
            current_path.unlink(missing_ok=True)
            logger.error(traceback.format_exc())
            jobs_failed.append((func, kwargs))
            continue
        else:
            jobs_done.append((func, kwargs))

    return {
        "jobs_done": jobs_done,
        "jobs_failed": jobs_failed,
    }
