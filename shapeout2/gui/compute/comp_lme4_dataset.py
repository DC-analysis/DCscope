import importlib.resources

from PyQt6 import uic, QtGui, QtWidgets

from ... import meta_tool


class LME4Dataset(QtWidgets.QDialog):
    def __init__(self, parent, slot, *args, **kwargs):
        super(LME4Dataset, self).__init__(parent, *args, **kwargs)
        ref = importlib.resources.files(
            "shapeout2.gui.compute") / "comp_lme4_dataset.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        self.identifier = slot.identifier

        # set dataset label
        self.checkBox_dataset.setText(slot.name)

        # set region icon
        region = meta_tool.get_info(slot.path,
                                    section="setup",
                                    key="chip region")
        icon = QtGui.QIcon.fromTheme("region_{}".format(region))
        pixmap = icon.pixmap(16)
        self.label_region.setPixmap(pixmap)
        self.label_region.setToolTip(region)

    def add_to_rlme4(self, pipeline, rlme4):
        """Add the dataset to an Rlme4 analysis

        Parameters
        ----------
        pipeline: shapeout2.pipeline.core.Pipeline
            The pipeline from which to extract the filtered dataset
            using `self.identifier`.
        rlme4: dclab.lme4.wrapr.Rlme4
            The analysis to which to append this dataset.

        Notes
        -----
        If the check box is not checked, then the dataset is ignored.
        """
        if self.checkBox_dataset.isChecked():
            ds_index = pipeline.slot_ids.index(self.identifier)
            ds = pipeline.get_dataset(ds_index)
            group_id = self.comboBox_group.currentIndex()
            group = "control" if group_id == 0 else "treatment"
            repetition = self.spinBox_repeat.value()
            rlme4.add_dataset(ds=ds, group=group, repetition=repetition)
