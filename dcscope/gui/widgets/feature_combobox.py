import dclab
from PyQt6 import QtCore, QtGui, QtWidgets

#: These are features only visible in developer mode
HIDDEN_FEATURES = []
for ii in range(10):
    HIDDEN_FEATURES.append(f"basinmap{ii}")


class FeatureComboBox(QtWidgets.QComboBox):
    def __init__(self, *args, **kwargs):
        """A DC data aware combobox for displaying DC features

        The combobox uses different colors to indicate the
        availability of features. Features can be ancillary,
        innate, basin-based, etc.

        This class serves as a drop-in replacement for QComboBox
        with a few special properties:

        - Call `set_dataset` with an instance of RTDCBase and the
          list of options is automatically populated with the values
          for this dataset, including coloring based on feature origin.
        - Features defined in :const:`HIDDEN_FEATURES` are not shown in
          the combobox if "advanced/developer mode" is not set in the
          settings.
        - Make sure to use `findData` and don't rely on any external
          lists when using `addItem`, because some of the items may
          not be added as explained in the previous point.
        """
        super(FeatureComboBox, self).__init__(*args, **kwargs)
        self.rtdc_ds = None
        self.default_choices = []

        # determine whether we should hide certain features
        settings = QtCore.QSettings()
        devmode = bool(int(settings.value("advanced/developer mode", 0)))
        self.hidden_feats = HIDDEN_FEATURES if not devmode else []

        # where the data are
        self.data_role = QtCore.Qt.ItemDataRole.UserRole

        # Set background color to white
        pal = self.palette()
        pal.setColor(self.backgroundRole(), QtGui.QColor(255, 255, 255))

    def addItem(self, text, userData=None):
        if userData not in self.hidden_feats:
            super(FeatureComboBox, self).addItem(text, userData)

    def currentData(self, role=None):
        if role is None:
            role = self.data_role
        return super(FeatureComboBox, self).currentData(role)

    def findData(self, data, role=None, *args, **kwargs):
        if role is None:
            role = self.data_role
        return super(FeatureComboBox, self).findData(data, role=role,
                                                     *args, **kwargs)

    def set_dataset(self, rtdc_ds):
        self.rtdc_ds = rtdc_ds
        self.update_feature_list()

    @QtCore.pyqtSlot()
    def update_feature_list(self):
        """Update the colors of all features in the combobox"""
        if self.rtdc_ds is None:
            raise ValueError("Please call `set_dataset` first!")
        # axes combobox choices
        ds_feats = self.rtdc_ds.features_scalar
        # remove hidden features
        [ds_feats.remove(f) for f in self.hidden_feats if f in ds_feats]
        ds_labels = [dclab.dfn.get_feature_label(f) for f in ds_feats]
        ds_colors = []
        ds_tips = []
        feats_loaded = self.rtdc_ds.features_loaded
        feats_ancillary = self.rtdc_ds.features_ancillary
        feats_basin = self.rtdc_ds.features_basin
        for feat in ds_feats:
            if feat in feats_loaded:
                ds_colors.append("#D2FFC8")
                ds_tips.append("feature data loaded")
            elif feat in feats_basin:
                ds_colors.append("#C0E8FF")
                ds_tips.append("feature data located in basin")
            elif feat in feats_ancillary:
                ds_colors.append("#FFD9C1")
                ds_tips.append("feature data needs to be computed")
            else:
                # fall-back
                ds_colors.append("#A9A9A9")
                ds_tips.append("unknown location of feature data")

        ds_fl = sorted(zip(ds_labels, ds_feats, ds_colors, ds_tips))

        # Remember current index. If it is -1, we can select a best feature
        # based on self.default_choices in the end.
        idx_cur = self.currentIndex()

        # Remember user selection. If it exists in ds_feats, the selection
        # will persist even if the user switches the dataset.
        feat_cur = self.currentData(self.data_role)

        blocked = self.signalsBlocked()  # remember block state
        self.blockSignals(True)

        # set features
        self.clear()
        model = self.model()
        for (label, feat, color, tip) in ds_fl:
            item = QtGui.QStandardItem(label)
            item.setData(feat, self.data_role)
            item.setBackground(QtGui.QColor(color))
            item.setForeground(QtGui.QColor("black"))
            item.setToolTip(tip)
            model.appendRow(item)

        if feat_cur and feat_cur in ds_feats:
            # If the previous selection exists in the new feature list, set it.
            idx_cur = self.findData(feat_cur)
        else:
            # If the previous selection does not exist in the new feature list,
            # select the first available feature in `default_choices`
            idx_cur = -1

        if idx_cur < 0:
            # If no selection made by user, select the first available feature
            # in `default_choices`
            for choice in self.default_choices:
                idx_choice = self.findData(choice)
                if idx_choice >= 0:
                    idx_cur = idx_choice
                    break

        self.setCurrentIndex(idx_cur)

        # set previous selection
        self.blockSignals(blocked)
