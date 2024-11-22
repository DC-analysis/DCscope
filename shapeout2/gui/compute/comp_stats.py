import codecs
import numbers
import pathlib
import importlib.resources
import time

import dclab
from PyQt6 import uic, QtCore, QtWidgets

from ..widgets import show_wait_cursor
from ..widgets.feature_combobox import HIDDEN_FEATURES
from ..._version import version

STAT_METHODS = sorted(dclab.statistics.Statistics.available_methods.keys())
STAT_METHODS.remove("%-gated")  # This does not make sense with Pipeline


class ComputeStatistics(QtWidgets.QDialog):
    def __init__(self, parent, pipeline, *args, **kwargs):
        super(ComputeStatistics, self).__init__(parent=parent, *args, **kwargs)
        ref = importlib.resources.files(
            "shapeout2.gui.compute") / "comp_stats.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        # for external statistics
        self.path = None
        # set pipeline
        self.pipeline = pipeline
        # Signals
        self.pushButton_path.clicked.connect(self.on_browse)
        self.comboBox.currentIndexChanged.connect(self.on_combobox)
        # Populate statistics methods
        self.bulklist_stats.set_title("Statistical methods")
        self.bulklist_stats.set_items(STAT_METHODS)
        self.bulklist_stats.on_select_all()
        # Populate filter ray comboBox
        self.comboBox_filter_ray.clear()
        self.comboBox_filter_ray.addItem("No filtering", None)
        for ii, slot in enumerate(pipeline.slots):
            if slot.slot_used:
                raytext = "Ray {} ({})".format(ii, slot.name)
                self.comboBox_filter_ray.addItem(raytext, slot.identifier)
        # initialize feature list
        self.bulklist_features.set_title("Features")
        # initialize rest
        if len(self.pipeline.slots) == 0:
            self.comboBox.setCurrentIndex(1)
        else:
            self.comboBox.setCurrentIndex(0)
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
        features = self.bulklist_features.get_selection()
        # get methods
        methods = self.bulklist_stats.get_selection()
        prog = QtWidgets.QProgressDialog("Computing statistics...", "Abort", 1,
                                         1, self)
        prog.setMinimumDuration(0)
        time.sleep(0.01)
        prog.setValue(0)
        # compute statistics
        values = []
        if self.comboBox.currentIndex() == 0:
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
                ds = dclab.new_dataset(pp)
                title = ds.title
                slot_id = self.comboBox_filter_ray.currentData()
                if slot_id is not None:
                    ds = self.pipeline.apply_filter_ray(rtdc_ds=ds,
                                                        slot_id=slot_id)
                    title += " ({})".format(slot_id)
                h, v = dclab.statistics.get_statistics(ds,
                                                       methods=methods,
                                                       features=features)
                h = ["Path", "Name"] + h
                v = ["{}".format(pp), title] + v
                values.append(v)
                prog.setValue(ii + 1)
                QtWidgets.QApplication.processEvents(
                    QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)

        # Header
        header = ["Statistics Output",
                  "Shape-Out {}".format(version),
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
            self.lineEdit_path.setText(self.path)
            self.comboBox.setCurrentIndex(1)
        else:
            self.path = None
            self.comboBox.setCurrentIndex(0)

    @QtCore.pyqtSlot()
    def on_combobox(self):
        if self.comboBox.currentIndex() == 1:
            # Datasets from a folder
            self.widget_other.show()
            if self.path is None:
                self.on_browse()
            if self.path:
                self.update_feature_list(use_pipeline=False)
                # else, on_combobox is triggered again
        else:
            # Datasets from current session
            self.widget_other.hide()
            self.update_feature_list(use_pipeline=True)

    @QtCore.pyqtSlot()
    def on_select_features_innate(self):
        """Only select all innate features of the first dataset"""

        if self.pipeline.num_slots:
            ds = self.pipeline.get_dataset(0)
            features_innate = ds.features_innate
            lw = self.bulklist_features.listWidget
            for ii in range(lw.count()):
                wid = lw.item(ii)
                for feat in features_innate:
                    if wid.data(101) == feat:
                        wid.setCheckState(QtCore.Qt.CheckState.Checked)
                        break
                else:
                    wid.setCheckState(QtCore.Qt.CheckState.Unchecked)

    def update_feature_list(self, use_pipeline=True):
        if use_pipeline:
            self.features = self.pipeline.get_features(scalar=True,
                                                       union=True,
                                                       label_sort=True)
        else:
            # We want to compute statistics from a folder
            # TODO:
            # - Add ml_score_??? features

            # label-sorted features
            features = dclab.dfn.scalar_feature_names
            labs = [dclab.dfn.get_feature_label(f) for f in features]
            lf = sorted(zip(labs, features))
            self.features = [it[1] for it in lf]

        # do not compute statistics for basinmap features
        for feat in HIDDEN_FEATURES + ["index"]:
            if feat in self.features:
                self.features.remove(feat)

        labels = [dclab.dfn.get_feature_label(feat) for feat in self.features]
        self.bulklist_features.set_items(self.features, labels)
