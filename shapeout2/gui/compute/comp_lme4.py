import importlib.resources
import webbrowser

from dclab import lme4
from PyQt6 import uic, QtCore, QtGui, QtWidgets

from .comp_lme4_dataset import LME4Dataset
from .comp_lme4_results import Rlme4ResultsDialog

from ..widgets import ShowWaitCursor


class ComputeSignificance(QtWidgets.QDialog):
    def __init__(self, parent, pipeline, *args, **kwargs):
        super(ComputeSignificance, self).__init__(parent, *args, **kwargs)
        ref = importlib.resources.files(
            "shapeout2.gui.compute") / "comp_lme4.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        # set pipeline
        self.pipeline = pipeline

        # populate feature combo box
        feats, labs = pipeline.get_features(scalar=True, label_sort=True,
                                            union=False, ret_labels=True)
        for feat, lab in zip(feats, labs):
            self.comboBox_feat.addItem(lab, feat)

        # populate datasets
        self.datasets = []
        for slot in self.pipeline.slots:
            dw = LME4Dataset(self, slot=slot)
            self.dataset_layout.addWidget(dw)
            self.datasets.append(dw)
        spacer = QtWidgets.QSpacerItem(20, 0,
                                       QtWidgets.QSizePolicy.Policy.Minimum,
                                       QtWidgets.QSizePolicy.Policy.Expanding)
        self.dataset_layout.addItem(spacer)
        self.update()

        # button signals
        btn_close = self.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Close)
        btn_close.clicked.connect(self.on_close)
        btn_close.setToolTip("Close this dialog")
        closeicon = QtGui.QIcon.fromTheme("dialog-close")
        btn_close.setIcon(closeicon)
        btn_openlme4 = self.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Apply)
        btn_openlme4.clicked.connect(self.on_lme4)
        btn_openlme4.setToolTip("Perform lme4 analysis")
        btn_openlme4.setText("Run R-lme4")
        picon = QtGui.QIcon.fromTheme("rlang")
        btn_openlme4.setIcon(picon)
        btn_help = self.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Help)
        btn_help.clicked.connect(self.on_help)
        btn_help.setToolTip("View R-lme4 Quick Guide online")
        helpicon = QtGui.QIcon.fromTheme("documentinfo")
        btn_help.setIcon(helpicon)

    @property
    def feature(self):
        return self.comboBox_feat.currentData()

    @property
    def model(self):
        if self.radioButton_lmer.isChecked():
            return "lmer"
        else:
            return "glmer+loglink"

    @QtCore.pyqtSlot()
    def on_lme4(self, ret_dlg=False):
        """Run lme4 analysis

        Parameters
        ----------
        ret_dlg: bool
            If set to True, then the dialog is returned without
            `_exec`uting it (used for testing).
        """
        self.setEnabled(False)
        # set R HOME from settings
        settings = QtCore.QSettings()
        r_path = settings.value("lme4/r path", "")
        if r_path:
            lme4.set_r_path(r_path)
        r_libs_path = settings.value("lme4/r libs user", "")
        if r_libs_path:
            lme4.set_r_lib_path(r_libs_path)
        # compute LMM
        with ShowWaitCursor():
            rlme4 = lme4.Rlme4(model=self.model, feature=self.feature)
            for wds in self.datasets:
                wds.add_to_rlme4(self.pipeline, rlme4)
            result = rlme4.fit()
        self.setEnabled(True)
        dlg = Rlme4ResultsDialog(self, result)
        if ret_dlg:
            return dlg
        else:
            dlg.exec()

    @QtCore.pyqtSlot()
    def on_close(self):
        """Close window"""
        self.close()

    @QtCore.pyqtSlot()
    def on_help(self):
        """Show Shape-Out 2 docs"""
        webbrowser.open(
            "https://dclab.readthedocs.io/en/stable/sec_av_lme4.html")
