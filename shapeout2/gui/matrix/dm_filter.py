import importlib.resources

from PyQt6 import uic, QtCore, QtWidgets

from ... import pipeline


class MatrixFilter(QtWidgets.QWidget):
    active_toggled = QtCore.pyqtSignal()
    enabled_toggled = QtCore.pyqtSignal(bool)
    option_action = QtCore.pyqtSignal(str)
    modify_clicked = QtCore.pyqtSignal(str)

    def __init__(self, identifier=None, state=None, *args, **kwargs):
        super(MatrixFilter, self).__init__(*args, **kwargs)
        ref = importlib.resources.files(
            "shapeout2.gui.matrix") / "dm_filter.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        # options button
        menu = QtWidgets.QMenu()
        menu.addAction('duplicate', self.action_duplicate)
        menu.addAction('remove', self.action_remove)
        self.toolButton_opt.setMenu(menu)

        # toggle all active, all inactive, semi state
        self.toolButton_toggle.clicked.connect(self.active_toggled.emit)

        # toggle enabled/disabled state
        self.checkBox.clicked.connect(self.on_enabled_toggled)

        # modify filter button
        self.toolButton_modify.clicked.connect(self.on_modify)

        if state is None:
            filt = pipeline.Filter._instances[identifier]
            self.identifier = identifier
            self.name = filt.name
            # set tooltip/label
            self.update_content()
        else:
            self.__setstate__(state)

    def __getstate__(self):
        state = {"enabled": self.enabled,
                 "identifier": self.identifier,
                 "name": self.name,
                 }
        return state

    def __setstate__(self, state):
        if state["identifier"] not in pipeline.Filter._instances:
            # Create a new filter with the identifier
            pipeline.Filter(identifier=state["identifier"])
        self.identifier = state["identifier"]
        self.enabled = state["enabled"]
        self.name = state["name"]
        self.update_content()

    @property
    def enabled(self):
        filt = pipeline.Filter._instances[self.identifier]
        return filt.general["enable filters"]

    @enabled.setter
    def enabled(self, b):
        filt = pipeline.Filter._instances[self.identifier]
        filt.general["enable filters"] = b

    @property
    def name(self):
        filt = pipeline.Filter._instances[self.identifier]
        return filt.name

    @name.setter
    def name(self, text):
        filt = pipeline.Filter._instances[self.identifier]
        filt.name = text

    def action_duplicate(self):
        self.option_action.emit("duplicate")

    def action_remove(self):
        self.option_action.emit("remove")

    def on_enabled_toggled(self, b):
        self.enabled = b
        self.enabled_toggled.emit(b)

    def on_modify(self):
        self.modify_clicked.emit(self.identifier)

    def set_label_string(self, string):
        if self.label.fontMetrics().boundingRect(string).width() < 60:
            nstring = string
        else:
            nstring = string + "..."
            while True:
                width = self.label.fontMetrics().boundingRect(nstring).width()
                if width > 60:
                    nstring = nstring[:-4] + "..."
                else:
                    break
        self.label.setText(nstring)

    @QtCore.pyqtSlot()
    def update_content(self):
        """Reset tool tips and title"""
        self.label.setToolTip(self.name)
        self.set_label_string(self.name)
        self.checkBox.blockSignals(True)
        self.checkBox.setChecked(self.enabled)
        self.checkBox.blockSignals(False)
        self.enabled_toggled.emit(self.enabled)
