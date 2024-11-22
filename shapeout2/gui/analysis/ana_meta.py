import numbers
import importlib.resources

import dclab
import numpy as np
from PyQt6 import uic, QtCore, QtWidgets

from ... import meta_tool


class MetaPanel(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(MetaPanel, self).__init__(*args, **kwargs)
        ref = importlib.resources.files(
            "shapeout2.gui.analysis") / "ana_meta.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        self.comboBox_slots.currentIndexChanged.connect(self.update_content)
        self.pipeline_state = None
        self.update_content()

    @property
    def current_slot_state(self):
        if self.pipeline_state is not None:
            slot_index = self.comboBox_slots.currentIndex()
            slot_state = self.pipeline_state["slots"][slot_index]
        else:
            slot_state = None
        return slot_state

    @property
    def slot_ids(self):
        """List of slot identifiers"""
        if self.pipeline_state is not None:
            ids = [ss["identifier"] for ss in self.pipeline_state["slots"]]
        else:
            ids = []
        return ids

    @property
    def slot_names(self):
        """List of slot names"""
        if self.pipeline_state is not None:
            nms = [ss["name"] for ss in self.pipeline_state["slots"]]
        else:
            nms = []
        return nms

    def update_info_box(self, group_box, config, section):
        """Populate an individual group box with keyword-value pairs"""
        group_box.layout().setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        # cleanup
        for ii in reversed(range(group_box.layout().count())):
            item = group_box.layout().itemAt(ii).widget()
            if item is not None:
                item.deleteLater()
        # populate
        items = sort_config_section_items(section, config[section].items())
        if items:
            for key, value in items:
                k, v, t = format_config_key_value(section, key, value)
                widget = QtWidgets.QWidget()
                hbox = QtWidgets.QHBoxLayout()
                hbox.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
                hbox.setContentsMargins(0, 0, 0, 0)
                ldescr = QtWidgets.QLabel(k + ": ")
                ldescr.setToolTip(f"{section}:{key}")
                ldescr.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
                hbox.addWidget(ldescr)
                lvalue = QtWidgets.QLabel(v)
                if t:
                    lvalue.setToolTip(t)
                lvalue.setAlignment(QtCore.Qt.AlignmentFlag.AlignBottom)
                hbox.addWidget(lvalue)
                widget.setLayout(hbox)
                group_box.layout().addWidget(widget)
            group_box.show()
        else:
            group_box.hide()

    def update_content(self, event=None, slot_index=None):
        if self.slot_ids:
            self.setEnabled(True)
            # update combobox
            self.comboBox_slots.blockSignals(True)
            if slot_index is None:
                slot_index = self.comboBox_slots.currentIndex()
                if slot_index > len(self.slot_ids) - 1 or slot_index < 0:
                    slot_index = len(self.slot_ids) - 1
            self.comboBox_slots.clear()
            self.comboBox_slots.addItems(self.slot_names)
            self.comboBox_slots.setCurrentIndex(slot_index)
            self.comboBox_slots.blockSignals(False)
            # populate content
            slot_state = self.pipeline_state["slots"][slot_index]
            cfg = meta_tool.get_rtdc_config(slot_state["path"])
            self.update_info_box(self.groupBox_experiment, cfg,
                                 "experiment")
            self.update_info_box(self.groupBox_pipeline, cfg,
                                 "pipeline")
            self.update_info_box(self.groupBox_fluorescence, cfg,
                                 "fluorescence")
            self.update_info_box(self.groupBox_imaging, cfg,
                                 "imaging")
            self.update_info_box(self.groupBox_online_contour, cfg,
                                 "online_contour")
            self.update_info_box(self.groupBox_online_filter, cfg,
                                 "online_filter")
            self.update_info_box(self.groupBox_setup, cfg,
                                 "setup")
            self.update_info_box(self.groupBox_user, cfg,
                                 "user")
        else:
            self.setEnabled(False)


def format_config_key_value(section, key, value):
    dtype = dclab.dfn.get_config_value_type(section, key)
    descr = dclab.dfn.get_config_value_descr(section, key)
    tip = ""
    # Value formatting
    if dtype == numbers.Number:  # pretty-print floats
        if abs(value) < 1e-12:
            # small enough to be considered zero for all metadata
            string = "0.0"
        else:
            # determine number of decimals
            dec = int(np.ceil(np.log10(1/np.abs(value))))
            if dec < 0:
                dec = 0
            string = ("{:." + "{}".format(dec + 2) + "f}").format(value)
    else:
        string = str(value)

    # Special cases
    if section == "experiment":
        if key in ["date", "time"]:
            descr, form = descr.split("(")
            tip = form.strip("()'")
        elif key == "sample":
            descr = "Sample name"
    elif section == "online_filter":
        if key.endswith("polygon points"):
            # format polygon points
            descr = "\n".join(descr.split(" ", 1))
            string = "\n".join([f"({x:.5g}, {y:.5g})" for x, y in value])
        elif key.endswith("soft limit"):
            descr = "\n".join(descr.split(", polygon ", 1))
    elif section == "setup":
        if key == "chip region":
            descr = descr.split(" (")[0]
        elif key == "medium" and string == "CellCarrierB":
            string = "CellCarrier B"
        elif key == "module composition":
            descr = "Modules used"
            string = ", ".join(string.split(","))
        elif key == "software version":
            descr = "Software"

    # Units
    if descr.endswith("]"):
        descr, units = descr.rsplit(" [", 1)
        units = units.strip("] ")
        string += " " + units

    return descr, string, tip


def sort_config_section_items(section, items):
    if section == "experiment":
        order = ["sample", "run index", "event count", "date", "time"]
    elif section == "pipeline":
        order = ["dcnum generation",
                 "dcnum data",
                 "dcnum background",
                 "dcnum segmenter",
                 "dcnum feature",
                 "dcnum gate",
                 "dcnum hash",
                 "dcnum mapping",
                 "dcnum yield",
                 ]
    elif section == "setup":
        order = ["medium", "channel width"]
    else:
        order = None

    if order is None:
        sitems = items
    else:
        sitems = []
        for key in order:
            for item in items:
                if key == item[0]:
                    sitems.append(item)
                    break
        # append those not in `order`
        for item in items:
            if item not in sitems:
                sitems.append(item)
    return sitems
