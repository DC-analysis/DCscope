import importlib.resources

from PyQt6 import uic, QtCore, QtWidgets

import dclab

from ..widgets import RangeControl
from ... import idiom


class FilterPanel(QtWidgets.QWidget):
    """Filter panel widget

    The filtering panel visualizes the properties of a
    :class:`dcscope.pipeline.filter.Filter` instance,
    i.e. box filters, list of polygon filters, filter
    name, etc. Their `__getstate__` and `__setstate__`
    functions are compatible.
    """
    #: Emitted when the user wants to create a new polygon filter
    request_new_polygon_filter = QtCore.pyqtSignal()

    # widgets emit these whenever they changed the pipeline
    pp_mod_send = QtCore.pyqtSignal(dict)
    # widgets receive these so they can reflect the pipeline changes
    pp_mod_recv = QtCore.pyqtSignal(dict)

    def __init__(self, *args, **kwargs):
        super(FilterPanel, self).__init__(*args, **kwargs)
        ref = importlib.resources.files(
            "dcscope.gui.analysis") / "ana_filter.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)
        # current DCscope pipeline
        self.pipeline = None

        self.setUpdatesEnabled(False)
        #: contains the range widgets for the box filters
        self._box_range_controls = {}
        self._populate_box_filters()
        self._polygon_checkboxes = {}
        self.update_polygon_filters()
        self.toolButton_duplicate.clicked.connect(self.on_duplicate_filter)
        self.toolButton_remove.clicked.connect(self.on_remove_filter)
        self.pushButton_apply.clicked.connect(self.write_filter)
        self.pushButton_reset.clicked.connect(self.update_content)

        self.comboBox_filters.currentIndexChanged.connect(self.update_content)
        self.toolButton_moreless.clicked.connect(self.on_moreless)
        self.label_box_edit.setVisible(False)
        self._box_edit_view = False
        self.setUpdatesEnabled(True)

        self.pp_mod_recv.connect(self.on_pp_mod_recv)

    def read_filter_state(self):
        state = {
            "filter used": self.checkBox_enable.isChecked(),
            "identifier": self.current_filter.identifier,
            "limit events bool": self.checkBox_limit.isChecked(),
            "limit events num": self.spinBox_limit.value(),
            "name": self.lineEdit_name.text(),
            "remove invalid events": self.checkBox_invalid.isChecked(),
        }
        # box filters
        box = {}
        for feat in self.active_box_features:
            rc = self._box_range_controls[feat]
            box[feat] = rc.read_pipeline_state()
        state["box filters"] = box
        # polygon filters
        pflist = []
        for key in self._polygon_checkboxes:
            if self._polygon_checkboxes[key].isChecked():
                pflist.append(key)
        state["polygon filters"] = pflist
        return state

    def write_filter_state(self, state):
        if self.current_filter.identifier != state["identifier"]:
            raise ValueError("Filter identifier mismatch!")
        self.checkBox_enable.setChecked(state["filter used"])
        self.lineEdit_name.setText(state["name"])
        self.checkBox_limit.setChecked(state["limit events bool"])
        self.spinBox_limit.setValue(state["limit events num"])
        self.checkBox_invalid.setChecked(state["remove invalid events"])
        # box filters
        box = state["box filters"]
        for feat in self._box_range_controls:
            rc = self._box_range_controls[feat]
            if feat in box:
                rc.show()
                rc.write_pipeline_state(box[feat])
            else:
                rc.setActive(False)  # uncheck range control (#67)
                rc.hide()
                rc.reset_range()

        # polygon filters
        pflist = state["polygon filters"]
        for key in self._polygon_checkboxes:
            if key in pflist:
                self._polygon_checkboxes[key].setChecked(True)
            else:
                self._polygon_checkboxes[key].setChecked(False)

    def _populate_box_filters(self):
        """Dynamically update available pipeline box filters

        This method can be called multiple times. If called multiple
        times, additional features that were not there before
        (e.g. `ml_score_???`) are added.
        """
        feats, labs = self.get_features_labels()

        self.verticalLayout_box.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        for lab, feat in sorted(zip(labs, feats)):
            integer = True if feat in idiom.INTEGER_FEATURES else False
            if feat not in self._box_range_controls:
                # Create the control
                rc = RangeControl(
                    self,
                    checkbox=False,  # checkbox is used in on_moreless
                    integer=integer,
                    label=lab,
                    data=feat)
                rc.setActive(False)
                rc.setVisible(False)
                # Insert the control at the correct position (label-sorted)
                rcf = list(self._box_range_controls.keys())
                rcl = [dclab.dfn.get_feature_label(ft) for ft in rcf]
                index = sorted(rcl + [lab]).index(lab)
                self.verticalLayout_box.insertWidget(index, rc)
                self._box_range_controls[feat] = rc

    @property
    def active_box_features(self):
        """List of box-filtered features that are active"""
        act = []
        for feat, item in self._box_range_controls.items():
            if item.is_active():
                act.append(feat)
        return act

    @property
    def current_filter(self):
        if self.filter_ids:
            filt_index = self.comboBox_filters.currentIndex()
            filt = self.pipeline.filters[filt_index]
        else:
            filt = None
        return filt

    @property
    def filter_ids(self):
        """List of filter identifiers"""
        if self.pipeline is not None:
            ids = [filt.identifier for filt in self.pipeline.filters]
        else:
            ids = []
        return ids

    def get_features_labels(self):
        """Wrapper around pipeline with default features if empty"""
        if self.pipeline is not None and self.pipeline.num_slots != 0:
            feats, labs = self.pipeline.get_features(scalar=True,
                                                     label_sort=True,
                                                     ret_labels=True,
                                                     union=True)
        else:
            # fallback (nothing in the pipeline or no pipeline)
            features = dclab.dfn.scalar_feature_names
            labs = [dclab.dfn.get_feature_label(f) for f in features]
            lf = sorted(zip(labs, features))
            feats = [it[1] for it in lf]
            labs = [it[0] for it in lf]
        return feats, labs

    @QtCore.pyqtSlot()
    def on_duplicate_filter(self):
        with self.pipeline.lock:
            filt_id = self.current_filter.identifier
            new_id = self.pipeline.duplicate_filter(filt_id)
            self.pp_mod_send.emit({"pipeline": {"filter_added": new_id}})

    @QtCore.pyqtSlot(dict)
    def on_pp_mod_recv(self, data):
        """We received a signal that something changed"""
        pp_dict = data.get("pipeline")
        if pp_dict:
            if self.isVisible():
                # If a filter is created, show it.
                filt_id = pp_dict.get("filter_added")
                if filt_id is not None:
                    filt_index = self.pipeline.filter_ids.index(filt_id)
                else:
                    filt_index = None
                self.update_content(filt_index)

        qv_dict = data.get("quickview")
        if qv_dict:
            if self.isVisible():
                # If quickview is clicked, show corresponding filter
                filt_index = qv_dict.get("filt_index")
                if filt_index is not None:
                    self.update_content(filt_index)

        if data.get("filter"):
            # filter changes without pipeline changes (e.g. PolygonFilter)
            self.update_polygon_filters()

    @QtCore.pyqtSlot()
    def on_remove_filter(self):
        with self.pipeline.lock:
            filt_id = self.current_filter.identifier
            self.pipeline.remove_filter(filt_id)
            self.pp_mod_send.emit({"pipeline": {"filter_removed": filt_id}})

    @QtCore.pyqtSlot()
    def on_moreless(self):
        """User wants to choose box filters"""
        if not self._box_edit_view:
            # get available features to show
            features, _ = self.get_features_labels()
            # create missing range controls if applicable (e.g. ml_score_???)
            self._populate_box_filters()
            # Show all filters shared by all datasets to the user
            for feat, rc in self._box_range_controls.items():
                if feat in features:
                    rc.setVisible(True)
                    rc.checkBox.setVisible(True)
                    rc.doubleSpinBox_min.setEnabled(False)
                    rc.doubleSpinBox_max.setEnabled(False)
                    rc.range_slider.setEnabled(False)
            self.toolButton_moreless.setText("...Finish editing")
            self.label_box_edit.setVisible(True)
            self._box_edit_view = True
        else:
            # Hide all filters that are not active
            for _, rc in self._box_range_controls.items():
                if not rc.is_active():
                    rc.setVisible(False)
                rc.checkBox.setVisible(False)
                rc.doubleSpinBox_min.setEnabled(True)
                rc.doubleSpinBox_max.setEnabled(True)
                rc.range_slider.setEnabled(True)
            self.toolButton_moreless.setText("Choose filters...")
            self.label_box_edit.setVisible(False)
            self._box_edit_view = False
            # Update box filter ranges
            self.update_box_ranges()

    def set_pipeline(self, pipeline):
        if self.pipeline is not None:
            raise ValueError("Pipeline can only be set once")
        self.pipeline = pipeline

    def show_filter(self, filt_id):
        self.update_content(filt_index=self.filter_ids.index(filt_id))

    @QtCore.pyqtSlot()
    def update_content(self, filt_index=None, **kwargs):
        if self.pipeline and self.pipeline.filters:
            # remember the previous filter index and make sure it is sane
            prev_index = self.comboBox_filters.currentIndex()
            if prev_index is None or prev_index < 0:
                prev_index = len(self.filter_ids) - 1

            self.setEnabled(True)
            self.update_polygon_filters()
            # update combobox
            self.comboBox_filters.blockSignals(True)
            if filt_index is None or filt_index < 0:
                # fallback to previous filter index
                filt_index = prev_index
            filt_index = min(filt_index, len(self.filter_ids) - 1)

            self.comboBox_filters.clear()
            self.comboBox_filters.addItems(
                [filt.name for filt in self.pipeline.filters])
            self.comboBox_filters.setCurrentIndex(filt_index)
            self.comboBox_filters.blockSignals(False)
            # populate content
            filt = self.pipeline.filters[filt_index]
            state = filt.__getstate__()
            self.write_filter_state(state)
            self.update_box_ranges()
        else:
            self.setEnabled(False)

    def update_box_ranges(self):
        """Update the box plot filter ranges

        Feature information is taken from the current pipeline.
        """
        if self.pipeline is not None and self.pipeline.num_slots:
            # compute min/max values
            mmdict = {}
            for feat in self.active_box_features:
                mmdict[feat] = self.pipeline.get_min_max(feat=feat)
            # update used features
            for feat in self._box_range_controls:
                rc = self._box_range_controls[feat]
                if feat in mmdict:
                    rc.setLimits(*mmdict[feat])
                if self.current_filter is not None:
                    state = self.current_filter.__getstate__()
                    if feat not in state["box filters"]:
                        # reset range to limits
                        rc.reset_range()

    def update_polygon_filters(self):
        """Update the layout containing the polygon filters"""
        self.verticalLayout_poly.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        # clear layout
        for ii in reversed(range(self.verticalLayout_poly.count())):
            item = self.verticalLayout_poly.itemAt(ii).widget()
            if item is not None:
                item.hide()
                item.deleteLater()
        self._polygon_checkboxes = {}  # must come after getting the state
        if dclab.PolygonFilter.instances:
            for pf in dclab.PolygonFilter.instances:
                widget = QtWidgets.QWidget()
                hbox = QtWidgets.QHBoxLayout()
                hbox.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
                hbox.setContentsMargins(0, 0, 0, 0)
                chb = QtWidgets.QCheckBox()
                hbox.addWidget(chb)
                hbox.addWidget(QtWidgets.QLabel(pf.name))
                widget.setLayout(hbox)
                self.verticalLayout_poly.addWidget(widget)
                self._polygon_checkboxes[pf.unique_id] = chb
        else:
            label = QtWidgets.QLabel("No polygon filters have been created "
                                     + "yet.")
            button = QtWidgets.QPushButton("Create polygon filter")
            button.clicked.connect(self.request_new_polygon_filter)
            self.verticalLayout_poly.addWidget(label)
            self.verticalLayout_poly.addWidget(button)

    @QtCore.pyqtSlot()
    def write_filter(self):
        """Update the dcscope.pipeline.Filter instance"""
        # get current index
        with self.pipeline.lock:
            filter_state = self.read_filter_state()
            filt_id = filter_state["identifier"]
            filt_index = self.pipeline.filter_ids.index(filt_id)
            self.pipeline.filters[filt_index].__setstate__(filter_state)
            self.pp_mod_send.emit({"pipeline": {"filter_modified": filt_id}})
