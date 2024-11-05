import pathlib
import importlib.resources

from PyQt6 import uic, QtWidgets

import dclab

from ... import session
from ...util import get_valid_filename


class ExportFilter(QtWidgets.QDialog):
    def __init__(self, parent, pipeline, file_format, *args, **kwargs):
        super(ExportFilter, self).__init__(parent=parent, *args, **kwargs)
        ref = importlib.resources.files("shapeout2.gui.export") / "e2filter.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        #: current analysis pipeline
        self.pipeline = pipeline
        #: export file format
        self.file_format = file_format

    @property
    def file_mode(self):
        if self.radioButton_single.isChecked():
            return "single"
        else:
            return "multiple"

    def done(self, r):
        if r:
            self.export_filters()
        super(ExportFilter, self).done(r)

    def export_filters(self):
        """Export filters"""
        if self.file_mode == "single":
            # all in one file
            if self.file_format == "poly":
                cap = "Polygon filter files (*.poly)"
                path, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self, 'Save polygon filters', '', cap)
                if not path.endswith(".poly"):
                    path += ".poly"
                dclab.PolygonFilter.save_all(path)
            else:
                cap = "Shape-Out 2 filter files (*.sof)"
                path, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self, 'Save polygon filters', '', cap)
                if not path.endswith(".sof"):
                    path += ".sof"
                session.export_filters(path=path,
                                       pipeline=self.pipeline)
        else:
            # one file per filter
            path = QtWidgets.QFileDialog.getExistingDirectory(self,
                                                              'Output Folder')
            if self.file_format == "poly":
                for pf in dclab.PolygonFilter.instances:
                    fn = "SO2-PolygonFilter_{}_{}.poly".format(pf.unique_id,
                                                               pf.name)
                    # remove bad characters from file name
                    fn = get_valid_filename(fn)
                    out = pathlib.Path(path) / fn
                    pf.save(out)
            else:
                for filt_index, filt_id in enumerate(self.pipeline.filter_ids):
                    filt = self.pipeline.filters[filt_index]
                    fn = "SO2-Filter_{}_{}.sof".format(filt_index, filt.name)
                    # remove bad characters from file name
                    fn = get_valid_filename(fn)
                    out = pathlib.Path(path) / fn
                    session.export_filters(path=out,
                                           pipeline=self.pipeline,
                                           filt_ids=[filt_id])
