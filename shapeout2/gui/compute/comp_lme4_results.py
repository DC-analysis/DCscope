import pathlib
import importlib.resources

import dclab
import numpy as np
from PyQt6 import uic, QtCore, QtGui, QtWidgets


class Rlme4ResultsDialog(QtWidgets.QDialog):
    def __init__(self, parent, rlme4_results, *args, **kwargs):
        super(Rlme4ResultsDialog, self).__init__(parent, *args, **kwargs)
        ref = importlib.resources.files(
            "shapeout2.gui.compute") / "comp_lme4_results.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        res = rlme4_results

        # parameters
        self.label_model.setText(res["model"])
        self.label_feature.setText(dclab.dfn.get_feature_label(res["feature"]))
        if res["is differential"]:
            self.label_differential.setText("Yes")
        else:
            self.label_differential.setText("No")

        # results
        if res["model converged"]:
            self.label_yes.show()
            self.label_no.hide()
        else:
            self.label_yes.hide()
            self.label_no.show()
        self.lineEdit_pvalue.setText(format_float(res["anova p-value"]))
        self.lineEdit_intercept.setText(
            format_float(res["fixed effects intercept"]))
        self.lineEdit_treatment.setText(
            format_float(res["fixed effects treatment"]))

        # summary text
        summary = []
        if res["lme4 messages"]:
            summary += ["lme4 messages"]
            summary += ["-------------"]
            summary += str(res["lme4 messages"]).split("\n")
            summary += "\n"
        summary += ["Model summary"]
        summary += ["-------------"]
        summary += self.parse_r_model_summary(
            str(res["r model summary"]).split("\n"))
        summary += "\n"
        summary += ["Coefficient table"]
        summary += ["-----------------"]
        summary += str(res["r model coefficients"]).split("\n")
        summary += "\n"
        summary += ["Anova test"]
        summary += ["----------"]
        summary += str(res["r anova"]).split("\n")
        excludelines = [
            "$repetition",
            'attr(,"clas',
            '[1] "coef.m',
            "Data: struc",
        ]
        summary = [ll for ll in summary if not ll[:11] in excludelines]

        self.summary = summary
        font = QtGui.QFont("Courier")
        self.plainTextEdit.setFont(font)
        self.plainTextEdit.setPlainText("\n".join(summary))

        # button signals
        btn_close = self.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Close)
        btn_close.clicked.connect(self.on_close)
        btn_close.setToolTip("Close this dialog")
        closeicon = QtGui.QIcon.fromTheme("dialog-close")
        btn_close.setIcon(closeicon)
        btn_openlme4 = self.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Apply)
        btn_openlme4.clicked.connect(self.on_save)
        btn_openlme4.setToolTip("Save report as text file")
        btn_openlme4.setText("Save report (.txt)")

    @staticmethod
    def parse_r_model_summary(slist):
        """Parse model summary from R (remove data lines)"""
        use = []
        just_data = False
        for line in slist:
            if line.startswith("   Data: "):
                just_data = True
            elif line.startswith("REML criterion "):
                just_data = False
            if not just_data:
                use.append(line)
        return use

    @QtCore.pyqtSlot()
    def on_close(self):
        """Close window"""
        self.close()

    @QtCore.pyqtSlot()
    def on_save(self):
        """Save summary text as .txt file"""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save summary", ".", "*.txt (*.txt files)")
        if path:
            path = pathlib.Path(path)
            if path.suffix != ".txt":
                path = path.with_name(path.name + ".txt")
            path.write_text("\n".join(self.summary))


def format_float(value):
    return np.format_float_positional(value,
                                      precision=5,
                                      fractional=False,
                                      trim="0")
