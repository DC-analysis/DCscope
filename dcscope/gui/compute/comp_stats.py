import codecs
import logging
import numbers
import pathlib
import time

import dclab
import h5py
from PyQt6 import QtCore, QtWidgets

from ..._version import version
from ..widgets import show_wait_cursor
from ..widgets.feature_combobox import HIDDEN_FEATURES
from .comp_stats_ui import Ui_Dialog


logger = logging.getLogger(__name__)

STAT_METHODS = sorted(dclab.statistics.Statistics.available_methods.keys())
STAT_METHODS.remove("%-gated")  # This does not make sense with Pipeline


def find_ml_score_features(path, callback=None):
    """Find all "ml_score_???" features in the .rtdc files in `path`

    Only the "events" group of the HDF5 files is checked (basins
    are not considered). Files that cannot be opened are ignored.

    Parameters
    ----------
    path: str or pathlib.Path
        Directory that is searched recursively for .rtdc files
    callback: callable
        Called with the arguments `(index, number_of_files)` after
        each file. If it returns True, the search is aborted.

    Returns
    -------
    features: list of str
        Sorted list of machine-learning score features
    """
    files = sorted(pathlib.Path(path).rglob("*.rtdc"))
    features = set()
    for ii, pp in enumerate(files):
        try:
            with h5py.File(pp, "r") as h5:
                if "events" in h5:
                    features.update(
                        feat for feat in h5["events"]
                        if (feat.startswith("ml_score_")
                            and dclab.dfn.scalar_feature_exists(feat)))
        except BaseException:
            pass
        if callback is not None and callback(ii + 1, len(files)):
            break
    return sorted(features)


class ComputeStatistics(QtWidgets.QDialog):
    def __init__(self, parent, pipeline, *args, **kwargs):
        super(ComputeStatistics, self).__init__(parent=parent, *args, **kwargs)

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        # for external statistics
        self.path = None
        #: machine-learning score features found in `self.path` (#108)
        self.features_ml = []
        # set pipeline
        self.pipeline = pipeline
        # Signals
        self.ui.pushButton_path.clicked.connect(self.on_browse)
        self.ui.pushButton_ml_search.clicked.connect(self.on_search_ml)
        self.ui.comboBox.currentIndexChanged.connect(self.on_combobox)
        # Populate statistics methods
        self.ui.bulklist_stats.set_title("Statistical methods")
        self.ui.bulklist_stats.set_items(STAT_METHODS)
        self.ui.bulklist_stats.on_select_all()
        # Populate filter ray comboBox
        self.ui.comboBox_filter_ray.clear()
        self.ui.comboBox_filter_ray.addItem("No filtering", None)
        for ii, slot in enumerate(pipeline.slots):
            if slot.slot_used:
                raytext = "Ray {} ({})".format(ii, slot.name)
                self.ui.comboBox_filter_ray.addItem(raytext, slot.identifier)
        # initialize feature list
        self.ui.bulklist_features.set_title("Features")
        # initialize rest
        if len(self.pipeline.slots) == 0:
            self.ui.comboBox.setCurrentIndex(1)
        else:
            self.ui.comboBox.setCurrentIndex(0)
        self.on_combobox()  # computes self.features
        # Only select innate features
        self.on_select_features_innate()

    def done(self, r):
        if r:
            success = self.export_statistics()
        else:
            success = True
        if success:
            super(ComputeStatistics, self).done(r)

    @show_wait_cursor
    @QtCore.pyqtSlot()
    def export_statistics(self):
        """Export statistics to .tsv"""
        # Output path
        opath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save statistics', '', 'tab-separated values (*.tsv)')
        if not opath:
            # Abort export
            return False
        elif not opath.endswith(".tsv"):
            opath += ".tsv"
        opath = pathlib.Path(opath)

        # get features
        features = self.ui.bulklist_features.get_selection()
        # get methods
        methods = self.ui.bulklist_stats.get_selection()
        prog = QtWidgets.QProgressDialog("Computing statistics...", "Abort", 1,
                                         1, self)
        prog.setMinimumDuration(0)
        time.sleep(0.01)
        prog.setValue(0)
        # compute statistics
        values = []
        #: files (datasets in a directory) that could not be read
        failed = []
        if self.ui.comboBox.currentIndex() == 0:
            # from pipeline
            prog.setMaximum(len(self.pipeline.slots))
            for slot_index in range(len(self.pipeline.slots)):
                slot = self.pipeline.slots[slot_index]
                if slot.slot_used:  # only export slots "used" (#15)
                    ds = self.pipeline.get_dataset(slot_index)
                    h, v = dclab.statistics.get_statistics(ds,
                                                           methods=methods,
                                                           features=features)
                    h = ["Path", "Slot", "Name"] + h
                    v = ["{}".format(ds.path), slot_index, slot.name] + v
                    values.append(v)
                if prog.wasCanceled():
                    break
                prog.setValue(slot_index + 1)
                QtWidgets.QApplication.processEvents(
                    QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
        else:
            # from path
            inpath = pathlib.Path(self.path)
            files = sorted(inpath.rglob("*.rtdc"))
            prog.setMaximum(len(files))
            for ii, pp in enumerate(files):
                try:
                    ds = dclab.new_dataset(pp)
                    title = ds.title
                    slot_id = self.ui.comboBox_filter_ray.currentData()
                    if slot_id is not None:
                        ds = self.pipeline.apply_filter_ray(rtdc_ds=ds,
                                                            slot_id=slot_id)
                        title += " ({})".format(slot_id)
                    h, v = dclab.statistics.get_statistics(
                        ds, methods=methods, features=features)
                except BaseException as e:
                    # Skip files that cannot be read (e.g. broken files)
                    # and tell the user about them below.
                    error = f"{type(e).__name__}: {e}"
                    logger.error(f"Could not compute statistics for "
                                 f"'{pp}': {error}")
                    failed.append((pp, error))
                else:
                    h = ["Path", "Name"] + h
                    v = ["{}".format(pp), title] + v
                    values.append(v)
                prog.setValue(ii + 1)
                QtWidgets.QApplication.processEvents(
                    QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)

        if failed:
            failed_text = "\n".join(
                f"- {pp}\n  ({error})" for pp, error in failed)
            QtWidgets.QMessageBox.warning(
                self,
                "Some files could not be read",
                "Statistics could not be computed for the following files, "
                f"which are not included in the output:\n\n{failed_text}")

        if not values:
            QtWidgets.QMessageBox.warning(
                self,
                "No statistics computed",
                "There are no datasets for which statistics could be "
                "computed. No file was written.")
            return False

        # Header
        header = ["Statistics Output",
                  "DCscope {}".format(version),
                  "",
                  "\t".join(h),
                  ]
        # Data
        data = []
        for v in values:
            line = []
            for vi in v:
                if (isinstance(vi, numbers.Real)
                        and not isinstance(vi, numbers.Integral)):
                    line.append("{:.5e}".format(vi))
                else:
                    line.append("{}".format(vi))
            data.append("\t".join(line))
        # Write BOM
        with opath.open("wb") as fd:
            fd.write(codecs.BOM_UTF8)
        # Write rest
        with opath.open("a", encoding="utf-8") as fd:
            for line in header:
                fd.write("# " + line + "\n")
            for line in data:
                fd.write(line + "\n")
        return True  # True means success

    @QtCore.pyqtSlot()
    def on_browse(self):
        out = QtWidgets.QFileDialog.getExistingDirectory(self,
                                                         'Export directory')
        if out:
            self.path = out
            self.features_ml = []
            self.ui.lineEdit_path.setText(self.path)
            self.ui.comboBox.setCurrentIndex(1)
        else:
            self.path = None
            self.ui.comboBox.setCurrentIndex(0)

    @QtCore.pyqtSlot()
    def on_combobox(self):
        if self.ui.comboBox.currentIndex() == 1:
            # Datasets from a folder
            self.ui.widget_other.show()
            if self.path is None:
                self.on_browse()
            if self.path:
                self.update_feature_list(use_pipeline=False)
                # else, on_combobox is triggered again
        else:
            # Datasets from current session
            self.ui.widget_other.hide()
            self.update_feature_list(use_pipeline=True)

    @QtCore.pyqtSlot()
    def on_search_ml(self):
        """Search `self.path` for machine-learning score features (#108)"""
        if not self.path:
            return
        prog = QtWidgets.QProgressDialog(
            "Searching for machine-learning features...", "Abort", 0, 1,
            self)
        prog.setMinimumDuration(0)

        def callback(index, size):
            prog.setMaximum(size)
            prog.setValue(index)
            QtWidgets.QApplication.processEvents(
                QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
            return prog.wasCanceled()

        self.features_ml = find_ml_score_features(self.path,
                                                  callback=callback)
        prog.close()
        self.update_feature_list(use_pipeline=False, keep_selection=True)
        self.ui.label_ml.setText(
            f"Machine-learning features ({len(self.features_ml)} found)")

    @QtCore.pyqtSlot()
    def on_select_features_innate(self):
        """Only select all innate features of the first dataset"""

        if self.pipeline.num_slots:
            ds = self.pipeline.get_dataset(0)
            features_innate = ds.features_innate
            lw = self.ui.bulklist_features.ui.listWidget
            for ii in range(lw.count()):
                wid = lw.item(ii)
                for feat in features_innate:
                    if wid.data(101) == feat:
                        wid.setCheckState(QtCore.Qt.CheckState.Checked)
                        break
                else:
                    wid.setCheckState(QtCore.Qt.CheckState.Unchecked)

    def update_feature_list(self, use_pipeline=True, keep_selection=False):
        """Update the list of features for which statistics are computed

        Parameters
        ----------
        use_pipeline: bool
            Whether to use the features of the datasets in the pipeline
            or (if False) all scalar features (for datasets in a
            directory)
        keep_selection: bool
            Whether to keep the current selection of features; the
            machine-learning features found in the directory are
            selected as well
        """
        if use_pipeline:
            self.features = self.pipeline.get_features(scalar=True,
                                                       union=True,
                                                       label_sort=True)
        else:
            # We want to compute statistics from a folder. The
            # machine-learning score features are not part of
            # `scalar_feature_names`; the user can search for them
            # in the directory (`on_search_ml`, #108).

            # label-sorted features
            features = (list(dclab.dfn.scalar_feature_names)
                        + [f for f in self.features_ml
                           if f not in dclab.dfn.scalar_feature_names])
            labs = [dclab.dfn.get_feature_label(f) for f in features]
            lf = sorted(zip(labs, features))
            self.features = [it[1] for it in lf]

        # do not compute statistics for basinmap features
        for feat in HIDDEN_FEATURES + ["index"]:
            if feat in self.features:
                self.features.remove(feat)

        labels = [dclab.dfn.get_feature_label(feat) for feat in self.features]
        selection = self.ui.bulklist_features.get_selection()
        self.ui.bulklist_features.set_items(self.features, labels)
        if keep_selection:
            selection += self.features_ml
            lw = self.ui.bulklist_features.ui.listWidget
            for ii in range(lw.count()):
                wid = lw.item(ii)
                if wid.data(101) in selection:
                    wid.setCheckState(QtCore.Qt.CheckState.Checked)
