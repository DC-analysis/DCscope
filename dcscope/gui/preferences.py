import os.path as os_path
import pathlib
import traceback

import platform

from dclab import cached
from dclab.rtdc_dataset.fmt_dcor import access_token
from dclab.lme4 import rsetup
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QStandardPaths

from ..extensions import ExtensionManager, SUPPORTED_FORMATS
from .widgets import show_wait_cursor
from .preferences_ui import Ui_Dialog


class ExtensionErrorWrapper:
    def __init__(self, ehash):
        self.ehash = ehash

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, trc):
        if exc_type is not None:
            QtWidgets.QMessageBox.warning(
                None,
                f"Loading extension {self.ehash} failed!",
                f"It was not possible to load the extension {self.ehash}! "
                + "You might have to install additional software:\n\n"
                + traceback.format_exc(),
            )
            return True  # do not raise the exception


class Preferences(QtWidgets.QDialog):
    """Preferences dialog to interact with QSettings"""
    instances = {}
    pp_mod_send = QtCore.pyqtSignal(dict)

    def __init__(self, parent, *args, **kwargs):
        super(Preferences, self).__init__(parent=parent, *args, **kwargs)

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.settings = QtCore.QSettings()
        self.parent = parent

        # Get default R path
        if rsetup.has_r():
            rdefault = str(rsetup.get_r_path())
        else:
            rdefault = ""

        store_keeper = cached.StoreKeeper.get_instance()
        cpath_act = store_keeper.disk_store.path

        #: configuration keys, corresponding widgets, and defaults
        self.config_pairs = [
            ["advanced/developer mode", self.ui.advanced_developer_mode, "0"],
            ["cache/disk store path", self.ui.lineEdit_cache_path, cpath_act],
            ["cache/disk store size", self.ui.doubleSpinBox_cache_disk_size, "9"],  # noqa: E501
            ["cache/memory num", self.ui.spinBox_cache_mem_num, "200"],
            ["cache/write interval", self.ui.spinBox_cache_interval, "30"],
            ["check for updates", self.ui.general_check_for_updates, "1"],
            ["dcor/api key", self.ui.dcor_api_key, ""],
            ["dcor/servers", self.ui.dcor_servers, ["dcor.mpl.mpg.de"]],
            ["dcor/use ssl", self.ui.dcor_use_ssl, "1"],
            ["gui/block matrix slot widget width",
             self.ui.spinBox_slot_widget_width, "65"],
            ["lme4/r path", self.ui.lme4_rpath, rdefault],
            ["s3/endpoint url", self.ui.lineEdit_s3_endpoint_url, ""],
            ["s3/access key id", self.ui.lineEdit_s3_access_key_id, ""],
            ["s3/secret access key", self.ui.lineEdit_s3_secret_access_key, ""],  # noqa: E501
        ]

        #: configuration signals that are emitted directly
        self.config_live_signals = {
            "gui/block matrix slot widget width":
                lambda v: {"block_matrix": {"slot widget width": v}}
        }

        # extensions
        store_path = os_path.join(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation), "extensions")
        self.extensions = ExtensionManager(store_path)

        self.ui.tabWidget.setCurrentIndex(0)
        self.reload()

        # signals
        self.btn_apply = self.ui.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Apply)
        self.btn_apply.clicked.connect(self.on_settings_apply)
        self.btn_cancel = self.ui.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.btn_ok = self.ui.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.btn_ok.clicked.connect(self.on_settings_apply)
        self.btn_restore = self.ui.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.RestoreDefaults)
        self.btn_restore.clicked.connect(self.on_settings_restore)
        # DCOR
        self.ui.pushButton_enc_token.clicked.connect(self.on_dcor_enc_token)
        # extension buttons
        self.ui.checkBox_ext_enabled.clicked.connect(self.on_ext_enabled)
        self.ui.pushButton_ext_load.clicked.connect(self.on_ext_load)
        self.ui.pushButton_ext_remove.clicked.connect(self.on_ext_remove)
        self.ui.listWidget_ext.currentRowChanged.connect(self.on_ext_selected)
        self.ui.listWidget_ext.itemChanged.connect(self.on_ext_modified)
        # lme4 buttons
        self.ui.pushButton_lme4_install.clicked.connect(self.on_lme4_install)
        self.ui.pushButton_lme4_search.clicked.connect(self.on_lme4_search_r)
        # cache
        self.ui.pushButton_cache_disk_clear.clicked.connect(
            self.on_cache_clear)
        self.ui.pushButton_cache_disk_browse.clicked.connect(
            self.on_cache_browse)
        # tab changed
        self.ui.tabWidget.currentChanged.connect(self.on_tab_changed)

    def reload(self):
        """Read configuration or set default parameters"""
        for key, widget, default in self.config_pairs:
            value = self.settings.value(key, default)
            if isinstance(widget, QtWidgets.QCheckBox):
                widget.setChecked(bool(int(value)))
            elif isinstance(widget, QtWidgets.QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QtWidgets.QSpinBox):
                widget.setValue(int(value))
            elif isinstance(widget, QtWidgets.QDoubleSpinBox):
                widget.setValue(float(value))
            elif widget is self.ui.dcor_servers:
                self.ui.dcor_servers.clear()
                self.ui.dcor_servers.addItems(value)
                self.ui.dcor_servers.setCurrentIndex(0)
            else:
                raise NotImplementedError("No rule for '{}'".format(key))

        # peculiarities of developer mode
        devmode = bool(int(self.settings.value("advanced/developer mode", 0)))
        self.ui.dcor_use_ssl.setVisible(devmode)  # show "use ssl" in dev mode

        if self.ui.tabWidget.currentWidget() is self.ui.tab_r:
            self.reload_lme4()

        self.reload_ext()

    def reload_ext(self):
        """Reload the list of extensions"""
        # extensions
        row = self.ui.listWidget_ext.currentRow()
        self.ui.listWidget_ext.blockSignals(True)
        self.ui.listWidget_ext.clear()
        have_extensions = bool(self.extensions)
        self.ui.widget_ext_controls.setVisible(have_extensions)
        if have_extensions:
            for ii, ext in enumerate(self.extensions):
                lwitem = QtWidgets.QListWidgetItem(ext.title,
                                                   self.ui.listWidget_ext)
                lwitem.setFlags(QtCore.Qt.ItemFlag.ItemIsEditable
                                | QtCore.Qt.ItemFlag.ItemIsSelectable
                                | QtCore.Qt.ItemFlag.ItemIsEnabled
                                | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                lwitem.setCheckState(QtCore.Qt.CheckState.Checked
                                     if ext.enabled
                                     else QtCore.Qt.CheckState.UnChecked)
                lwitem.setData(100, ext.hash)
            self.ui.listWidget_ext.setCurrentRow(0)
            if row + 1 > self.ui.listWidget_ext.count() or row < 0:
                row = 0
            self.ui.listWidget_ext.setCurrentRow(row)
        self.ui.listWidget_ext.blockSignals(False)
        self.on_ext_selected()

    @show_wait_cursor
    def reload_lme4(self, install=False):
        """Reload information about lme4, optionally installing it"""
        # Before we do anything, we have to find a persistent writable
        # location where we can install lme4 and set the environment variable
        # R_LIBS_USER accordingly.
        r_libs_user = self.settings.value("lme4/r libs user", None)
        if r_libs_user is None or not pathlib.Path(r_libs_user).exists():
            r_libs_user = pathlib.Path(
                QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.AppLocalDataLocation)
            ) / "r-libs"
            r_libs_user.mkdir(parents=True, exist_ok=True)
            r_libs_user = str(r_libs_user)
            self.settings.setValue("lme4/r libs user", r_libs_user)
        rsetup.set_r_lib_path(r_libs_user)

        # set the binary
        binary = self.ui.lme4_rpath.text()
        if pathlib.Path(binary).is_file():
            rsetup.set_r_path(binary)

        # enable/disable lme4-install button
        self.ui.pushButton_lme4_install.setEnabled(rsetup.has_r())

        # check lme4 package status
        if not rsetup.has_r():
            r_version = "unknown"
            lme4_st = "unknown"
        else:
            r_version = rsetup.get_r_version()
            if rsetup.has_lme4():
                lme4_st = "installed"
            else:
                lme4_st = "not installed"

        if install and lme4_st == "not installed":
            self.setEnabled(False)
            rsetup.require_lme4()
            self.setEnabled(True)
            # update interface with installed lme4
            self.reload_lme4(install=False)
        else:
            # update user interface
            self.ui.pushButton_lme4_install.setVisible(
                lme4_st == "not installed")
            self.ui.label_r_version.setText(r_version)
            self.ui.label_lme4_installed.setText(lme4_st)

    @QtCore.pyqtSlot()
    def on_cache_clear(self):
        """Clear the disk store cache"""
        store_keeper = cached.StoreKeeper.get_instance()
        store_keeper.disk_store.clear()
        store_keeper.disk_store.path.mkdir(parents=True, exist_ok=True)

    @QtCore.pyqtSlot()
    def on_cache_browse(self):
        """Choose a new caching location"""
        out = QtWidgets.QFileDialog.getExistingDirectory(self, 'Disk cache')
        if out:
            self.ui.lineEdit_cache_path.setText(out)

    @QtCore.pyqtSlot()
    def on_dcor_enc_token(self):
        """Load an encrypted DCOR access token and store the certificate"""
        # get path
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            parent=self,
            caption="SSpecify encrypted DCOR access token",
            directory=self.settings.value("paths/encrypted access token", ""),
            filter="DCOR access token (*.dcor-access)")
        if not path:
            return
        path = pathlib.Path(path)
        self.settings.setValue("paths/encrypted access token",
                               str(path.parent))
        # get password
        pwd, cont = QtWidgets.QInputDialog.getText(
            self,
            "Password required",
            f"Please enter the encryption password for {path.name}!",
            QtWidgets.QLineEdit.EchoMode.Password)
        pwd = pwd.strip()
        if not pwd or not cont:
            return
        # get info
        host = access_token.get_hostname(path, pwd)
        api_key = access_token.get_api_key(path, pwd)
        cert = access_token.get_certificate(path, pwd)
        # write certificate to our global DCscope certs directory
        ca_path = pathlib.Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation)
        ) / "certificates"
        (ca_path / f"{host}.cert").write_bytes(cert)
        # store other metadata
        self.settings.setValue("dcor/api key", api_key)

        servers = self.settings.value("dcor/servers", ["dcor.mpl.mpg.de"])
        if host in servers:
            servers.remove(host)
        servers.insert(0, host.strip("/"))
        self.settings.setValue("dcor/servers", servers)
        self.reload()

    @QtCore.pyqtSlot(bool)
    def on_ext_enabled(self, enabled):
        """Enable or disable an extension (signal from checkbox widget)"""
        item = self.ui.listWidget_ext.currentItem()
        ehash = item.data(100)
        with ExtensionErrorWrapper(ehash):
            self.extensions.extension_set_enabled(ehash, enabled)
        self.reload_ext()
        self.pp_mod_send.emit({"pipeline": {"extension_enabled": str(ehash)}})

    @QtCore.pyqtSlot()
    def on_ext_load(self):
        """Load an extension from the file system"""
        format_string = " ".join(f"*{su}" for su in SUPPORTED_FORMATS)
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            parent=self,
            caption="Select an extension file",
            directory=self.settings.value("paths/extension", ""),
            filter=f"Supported extension files ({format_string})")
        if paths:
            for pp in paths:
                with ExtensionErrorWrapper(pp):
                    self.extensions.import_extension_from_path(pp)
            self.reload_ext()
            self.pp_mod_send.emit(
                {"pipeline": {"extension_loaded": [str(p) for p in paths]}})

    @QtCore.pyqtSlot()
    def on_ext_remove(self):
        """Remove an extension"""
        ehash = self.ui.listWidget_ext.currentItem().data(100)
        self.extensions.extension_remove(ehash)
        self.reload_ext()
        self.pp_mod_send.emit({"pipeline": {"extension_removed": str(ehash)}})

    @QtCore.pyqtSlot(QtWidgets.QListWidgetItem)
    def on_ext_modified(self, item):
        """Enable or disable an extension (signal from listWidget)"""
        ehash = item.data(100)
        enabled = bool(item.checkState())
        with ExtensionErrorWrapper(ehash):
            self.extensions.extension_set_enabled(ehash, enabled)
        self.ui.listWidget_ext.setCurrentItem(item)
        self.reload_ext()
        self.pp_mod_send.emit({"pipeline": {"extension_modified": str(ehash)}})

    @QtCore.pyqtSlot()
    def on_ext_selected(self):
        """Display details for an extension (signal from listWidget)"""
        item = self.ui.listWidget_ext.currentItem()
        if item is not None:
            ehash = item.data(100)
            ext = self.extensions[ehash]
            self.ui.checkBox_ext_enabled.blockSignals(True)
            self.ui.checkBox_ext_enabled.setChecked(ext.enabled)
            self.ui.checkBox_ext_enabled.blockSignals(False)
            with ExtensionErrorWrapper(ehash):
                if ext.enabled:  # only load the extension if enabled
                    ext.load()
            self.ui.label_ext_name.setText(ext.title)
            item.setText(ext.title)
            self.ui.label_ext_description.setText(ext.description)

    @QtCore.pyqtSlot()
    def on_lme4_install(self):
        self.reload_lme4(install=True)

    @QtCore.pyqtSlot()
    def on_lme4_search_r(self):
        if platform.system() == "Windows":
            filters = "R executable (R.exe)"
        else:
            filters = "R executable (R)"
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Executable", ".", filters)
        if path:
            self.ui.lme4_rpath.setText(path)

    @QtCore.pyqtSlot()
    def on_settings_apply(self):
        """Save current changes made in UI to settings and reload UI"""
        restart_required = False
        for key, widget, default in self.config_pairs:
            if isinstance(widget, QtWidgets.QCheckBox):
                value = str(int(widget.isChecked()))
            elif isinstance(widget, QtWidgets.QLineEdit):
                value = widget.text().strip()
            elif isinstance(widget, QtWidgets.QSpinBox):
                value = str(widget.value())
            elif isinstance(widget, QtWidgets.QDoubleSpinBox):
                value = str(widget.value())
            elif widget is self.ui.dcor_servers:
                curtext = self.ui.dcor_servers.currentText()
                items = self.settings.value(key, default)
                if curtext in items:
                    # We do it again below to be on the safe side
                    items.remove(curtext)
                for bad_start in ["https://", "http://"]:
                    if curtext.startswith(bad_start):
                        curtext = curtext[len(bad_start):]
                if curtext in items:
                    # We do it again with the stripped version
                    items.remove(curtext)
                items.insert(0, curtext)
                value = items
            else:
                raise NotImplementedError("No rule for '{}'".format(key))

            if key in self.config_live_signals:
                if str(self.settings.value(key)) != str(value):
                    signal = self.config_live_signals[key](value)
                    self.pp_mod_send.emit(signal)

            # Determine whether restart is required
            if key == "advanced/developer mode":
                if value != self.settings.value(key, "0"):
                    restart_required = True
            elif key.startswith("cache/"):
                if self.settings.value(key) != str(value):
                    restart_required = True

            self.settings.setValue(key, value)

        if restart_required:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Icon.Information)
            msg.setText("Please restart DCscope for the changes "
                        + "to take effect.")
            msg.setWindowTitle("Restart DCscope")
            msg.exec()

        # reload UI to give visual feedback
        self.reload()

    @QtCore.pyqtSlot()
    def on_settings_restore(self):
        self.settings.clear()
        self.reload()

    @QtCore.pyqtSlot()
    def on_tab_changed(self):
        if self.ui.tabWidget.currentWidget() is self.ui.tab_extensions:
            # Managing extensions has nothing to do with other settings.
            enabled = False
        else:
            enabled = True

        if self.ui.tabWidget.currentWidget() is self.ui.tab_r:
            self.reload_lme4()

        self.btn_apply.setEnabled(enabled)
        self.btn_cancel.setEnabled(enabled)
        self.btn_restore.setEnabled(enabled)
