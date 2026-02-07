import importlib.resources
import json
import logging
import pathlib
import signal
import sys
import traceback
import warnings
import webbrowser

import dclab
from dclab.lme4 import rsetup
import h5py
import numpy
import scipy

from PyQt6 import uic, QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QMessageBox
import pyqtgraph as pg

from . import analysis
from . import bulk
from . import compute
from . import dcor
from . import export
from .helpers import connect_pp_mod_signals
from . import pipeline_plot
from . import preferences
from . import quick_view
from . import update
from . import widgets

from ..extensions import ExtensionManager
from .. import pipeline
from .. import session

from .._version import version

# global plotting configuration parameters
pg.setConfigOption("background", None)
pg.setConfigOption("foreground", "k")
pg.setConfigOption("antialias", True)
pg.setConfigOption("imageAxisOrder", "row-major")

# set Qt icon theme search path
ref = importlib.resources.files("dcscope.img") / "icon.png"
with importlib.resources.as_file(ref) as icon_path:
    theme_path = icon_path.with_name("icon-theme")
if theme_path.exists():
    QtGui.QIcon.setThemeSearchPaths([str(theme_path)])
    QtGui.QIcon.setThemeName(".")
else:
    warnings.warn("DCscope theme path not available")

logger = logging.getLogger(__name__)


class DCscope(QtWidgets.QMainWindow):
    plots_changed = QtCore.pyqtSignal()
    # widgets emit these whenever they changed the pipeline
    pp_mod_send = QtCore.pyqtSignal(dict)
    # widgets receive these so they can reflect the pipeline changes
    pp_mod_recv = QtCore.pyqtSignal(dict)

    def __init__(self, *arguments):
        """Initialize DCscope

        If you pass the "--version" command line argument, the
        application will print the version after initialization
        and exit.
        """
        super(DCscope, self).__init__()
        ref = importlib.resources.files("dcscope.gui") / "main.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        # pipeline
        self.pipeline = None
        self.widget_quick_view = None

        # update check
        self._update_thread = None
        self._update_worker = None
        # Settings are stored in the .ini file format. Even though
        # `self.settings` may return integer/bool in the same session,
        # in the next session, it will reliably return strings. Lists
        # of strings (comma-separated) work nicely though.
        QtCore.QCoreApplication.setOrganizationName("DC-analysis")
        QtCore.QCoreApplication.setOrganizationDomain("dc-cosmos.org")
        QtCore.QCoreApplication.setApplicationName("dcscope")
        QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)

        #: DCscope settings
        self.settings = QtCore.QSettings()
        # Register custom DCOR CA bundle directory with dclab
        ca_path = pathlib.Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation)
        ) / "certificates"
        ca_path.mkdir(exist_ok=True, parents=True)
        dclab.rtdc_dataset.fmt_dcor.DCOR_CERTS_SEARCH_PATHS.append(ca_path)
        # Register user-defined DCOR API Key in case the user wants to
        # open a session with private data.
        api_key = self.settings.value("dcor/api key", "")
        dclab.rtdc_dataset.fmt_dcor.api.APIHandler.add_api_key(api_key)
        # Register S3 access settings in dclab
        s3_endpoint_url = self.settings.value("s3/endpoint url", "")
        if s3_endpoint_url:
            dclab.rtdc_dataset.fmt_s3.S3_ENDPOINT_URL = s3_endpoint_url
        s3_access_key_id = self.settings.value("s3/access key id", "")
        if s3_access_key_id:
            dclab.rtdc_dataset.fmt_s3.S3_ACCESS_KEY_ID = s3_access_key_id
        s3_secret_access_key = self.settings.value("s3/secret access key", "")
        if s3_secret_access_key:
            dclab.rtdc_dataset.fmt_s3.S3_SECRET_ACCESS_KEY = \
                s3_secret_access_key

        #: Extensions
        store_path = pathlib.Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation)
        ) / "extensions"
        try:
            self.extensions = ExtensionManager(store_path)
        except BaseException:
            QtWidgets.QMessageBox.warning(
                self,
                "Extensions automatically disabled",
                "Some extensions could not be loaded and were disabled:\n\n"
                + traceback.format_exc(),
            )
        # GUI
        self.setWindowTitle(f"DCscope {version}")
        # Disable native menu bar (e.g. on Mac)
        self.menubar.setNativeMenuBar(False)
        # File menu
        self.actionLoadDataset.triggered.connect(self.add_dataslot)
        self.actionLoadDCOR.triggered.connect(self.on_action_dcor)
        self.actionClearDatasets.triggered.connect(
            self.on_action_clear_datasets)
        self.actionClearSession.triggered.connect(self.on_action_clear)
        self.actionOpenSession.triggered.connect(self.on_action_open)
        self.actionSaveSession.triggered.connect(self.on_action_save)
        # Edit menu
        self.actionChangeDatasetOrder.triggered.connect(
            self.on_action_change_dataset_order)
        self.actionPreferences.triggered.connect(self.on_action_preferences)
        # Bulk action menu
        self.actionComputeEmodulus.triggered.connect(
            self.on_action_compute_emodulus)
        # Compute menu
        self.actionComputeStatistics.triggered.connect(
            self.on_action_compute_statistics)
        self.actionComputeSignificance.triggered.connect(
            self.on_action_compute_significance)
        # Export menu
        # data
        self.actionExportData.triggered.connect(self.on_action_export_data)
        # filters
        self.action_export_filter_polygon.triggered.connect(
            self.on_action_export_filter_polygon)
        self.action_export_filter_pipeline.triggered.connect(
            self.on_action_export_filter_pipeline)
        self.action_export_filter_ray_dataset.triggered.connect(
            self.on_action_export_filter_ray_dataset)
        # plot
        self.actionExportPlot.triggered.connect(self.on_action_export_plot)
        # Import menu
        self.actionImportFilter.triggered.connect(self.on_action_import_filter)
        # Help menu
        self.actionDocumentation.triggered.connect(self.on_action_docs)
        self.actionSoftware.triggered.connect(self.on_action_software)
        self.actionAbout.triggered.connect(self.on_action_about)
        # Subwindows
        self.subwindows = {}
        # Subwindows for plots
        self.subwindows_plots = {}
        # Initialize a few things
        self.init_quick_view()
        self.init_analysis_view()
        self.mdiArea.cascadeSubWindows()

        # BLOCK MATRIX (wraps DataMatrix and PlotMatrix)
        # BlockMatrix appearance
        self.toolButton_dm.clicked.connect(self.on_block_matrix)
        self.splitter.splitterMoved.connect(self.on_splitter)
        # BlockMatrix Actions
        self.actionNewFilter.triggered.connect(self.add_filter)
        self.actionNewPlot.triggered.connect(self.add_plot)
        self.block_matrix.toolButton_load_dataset.clicked.connect(
            self.add_dataslot)
        self.block_matrix.toolButton_new_filter.clicked.connect(
            self.add_filter)
        self.block_matrix.toolButton_new_plot.clicked.connect(
            self.add_plot)
        # BlockMatrix default state
        self.toolButton_new_plot.setEnabled(False)
        self.block_matrix.toolButton_new_plot.setEnabled(False)
        # BlockMatrix other signals
        self.block_matrix.slot_modify_clicked.connect(self.on_modify_slot)
        self.block_matrix.filter_modify_clicked.connect(self.on_modify_filter)
        self.block_matrix.plot_modify_clicked.connect(self.on_modify_plot)

        # QUICK VIEW
        # polygon filter creation
        self.widget_quick_view.polygon_filter_about_to_be_deleted.connect(
            self.on_remove_polygon_filter_from_pipeline)

        # ANALYSIS VIEW
        # polygon filter creation
        self.widget_ana_view.widget_filter.request_new_polygon_filter.connect(
            self.on_new_polygon_filter)

        # Top of the pipeline modification hierarchy
        self.pp_mod_send.connect(self.on_pp_mod_recv)
        connect_pp_mod_signals(self, self.block_matrix)
        connect_pp_mod_signals(self, self.widget_quick_view)
        connect_pp_mod_signals(self, self.widget_ana_view)

        # Set analysis pipeline
        self.set_pipeline()

        # if "--version" was specified, print the version and exit
        if "--version" in arguments:
            print(version)
            QtWidgets.QApplication.processEvents(
                QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)
            sys.exit(0)
        else:
            # deal with any other arguments that might have been passed
            for arg in arguments:
                apath = pathlib.Path(arg)
                if apath.exists():
                    if apath.suffix == ".so2":
                        # load a session
                        self.on_action_open(path=apath)
                    elif apath.suffix == ".rtdc":
                        # add a dataslot
                        self.add_dataslot(paths=[apath])
                    elif apath.suffix in [".sof", ".poly"]:
                        # add a filter
                        self.on_action_import_filter(path=apath)

        # check for updates
        do_update = int(self.settings.value("check for updates", 1))
        self.on_action_check_update(do_update)

        # finalize
        self.show()
        self.raise_()
        self.activateWindow()
        self.showMaximized()
        self.setWindowState(QtCore.Qt.WindowState.WindowActive)

    @QtCore.pyqtSlot()
    def add_dataslot(self, paths=None, is_dcor=False):
        """Adds a dataslot to the pipeline

        Parameters
        ----------
        paths: list of str or list of pathlib.Path
            If specified, no file dialog is displayed and the files
            specified are loaded. Can also be DCOR URL.
        is_dcor: bool
            If set to True, `paths` will be treated as a list of
            DCOR URLs. Does not have any effect if `paths` is None.
        """
        if paths is None:
            fnames, _ = QtWidgets.QFileDialog.getOpenFileNames(
                parent=self,
                caption="Select an RT-DC measurement",
                directory=self.settings.value("paths/add dataset", ""),
                filter="RT-DC Files (*.rtdc)")
        else:
            fnames = paths

        if fnames:
            self.toolButton_new_plot.setEnabled(True)
            self.block_matrix.toolButton_new_plot.setEnabled(True)

        failed_paths = []

        slot_ids = []
        # Create Dataslot instance and update block matrix
        self.setUpdatesEnabled(False)
        with widgets.ShowWaitCursor():
            for fn in fnames:
                if is_dcor:
                    path = fn
                else:
                    path = pathlib.Path(fn)
                    self.settings.setValue("paths/add dataset",
                                           str(path.parent))
                # add a filter if we don't have one already
                if self.pipeline.num_filters == 0:
                    self.add_filter()
                try:
                    slot_id = self.pipeline.add_slot(path=path)
                except BaseException:
                    if len(fnames) == 1:
                        # Let the user know immediately
                        raise
                    else:
                        failed_paths.append(path)
                    continue

                slot_ids.append(slot_id)

        self.pipeline.compute_reduced_sample_names()

        self.pp_mod_send.emit({"pipeline": {"slots_added": slot_ids}})

        self.setUpdatesEnabled(True)
        self.repaint()

        # Update box filter limits
        self.widget_ana_view.widget_filter.update_box_ranges()
        # Update dataslot in analysis view
        self.widget_ana_view.widget_slot.update_content()

        if failed_paths:
            failed_text = ("The following files could not be loaded. You can "
                           "open them individually to see the corresponding "
                           "error message during loading.\n")
            for path in failed_paths:
                failed_text += f"- {path}\n"
            QtWidgets.QMessageBox.warning(self,
                                          "Failed to load some datasets",
                                          failed_text)

        return slot_ids

    @QtCore.pyqtSlot()
    def add_filter(self):
        """Add a filter using tool buttons"""
        filt_id = self.pipeline.add_filter()
        self.widget_ana_view.widget_filter.update_content()
        self.pp_mod_send.emit({"pipeline": {"filter_added": filt_id}})
        return filt_id

    @QtCore.pyqtSlot()
    def add_plot(self):
        plot_id = self.pipeline.add_plot()
        self.add_plot_window(plot_id)
        # update UI contents
        self.widget_ana_view.widget_plot.update_content()
        self.pp_mod_send.emit({"pipeline": {"plot_added": plot_id}})
        return plot_id

    @QtCore.pyqtSlot()
    def add_plot_window(self, plot_id):
        """Create a plot window if necessary and show it"""
        if plot_id in self.subwindows_plots:
            sub = self.subwindows_plots[plot_id]
        else:
            # create subwindow
            sub = widgets.MDISubWindowWOButtons(self)
            pw = pipeline_plot.PipelinePlot(parent=sub,
                                            pipeline=self.pipeline,
                                            plot_id=plot_id)
            self.plots_changed.connect(pw.update_content)
            sub.setWidget(pw)
            pw.update_content()
            self.mdiArea.addSubWindow(sub)
            self.subwindows_plots[plot_id] = sub
        sub.show()

    @QtCore.pyqtSlot(QtCore.QEvent)
    def closeEvent(self, event):
        """Determine what happens when the user wants to quit"""
        if self.pipeline.slots or self.pipeline.filters:
            if self.on_action_clear():
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    @QtCore.pyqtSlot(QtCore.QEvent)
    def dragEnterEvent(self, e):
        """Whether files are accepted"""
        if e.mimeData().hasUrls():
            e.accept()
        else:
            e.ignore()

    @QtCore.pyqtSlot(QtCore.QEvent)
    @widgets.show_wait_cursor
    def dropEvent(self, e):
        """Add dropped files to view"""
        urls = e.mimeData().urls()
        if urls:
            pathlist = []
            is_dcor = bool(urls[0].host())
            for ff in urls:
                if is_dcor:
                    # DCOR data
                    pathlist.append(ff.toString())
                else:
                    pp = pathlib.Path(ff.toLocalFile())
                    if pp.is_dir():
                        pathlist += list(pp.rglob("*.rtdc"))
                    elif pp.suffix == ".rtdc":
                        pathlist.append(pp)
                    pathlist = sorted(pathlist)
            if pathlist:
                self.add_dataslot(paths=pathlist, is_dcor=is_dcor)

    def init_analysis_view(self):
        sub = widgets.MDISubWindowWOButtons(self)
        self.widget_ana_view = analysis.AnalysisView(parent=self)
        sub.setWidget(self.widget_ana_view)
        self.subwindows["analysis_view"] = sub
        # signals
        self.toolButton_ana_view.toggled.connect(sub.setVisible)
        self.toolButton_ana_view.toggled.connect(
            self.widget_ana_view.on_visible)
        sub.hide()
        self.mdiArea.addSubWindow(sub)

    def init_quick_view(self):
        sub = widgets.MDISubWindowWOButtons(self)
        self.widget_quick_view = quick_view.QuickView(parent=self)
        sub.setWidget(self.widget_quick_view)
        self.subwindows["quick_view"] = sub
        # signals
        self.toolButton_quick_view.toggled.connect(sub.setVisible)
        sub.hide()
        self.mdiArea.addSubWindow(sub)

    @QtCore.pyqtSlot()
    def on_action_about(self):
        gh = "DC-analysis/DCscope"
        rtd = "dcscope.readthedocs.io"
        about_text = (
            f"DCscope is a graphical user interface for the analysis "
            f"and visualization of deformability cytometry data sets.<br><br>"
            f"Author: Paul Müller<br>"
            f"GitHub: <a href='https://github.com/{gh}'>{gh}</a><br>"
            f"Documentation: <a href='https://{rtd}'>{rtd}</a><br>"
        )
        QtWidgets.QMessageBox.about(self, f"DCscope {version}", about_text)

    @QtCore.pyqtSlot()
    def on_action_change_dataset_order(self):
        """Show dialog for changing dataset order"""
        dlg = analysis.DlgSlotReorder(self.pipeline, self)
        dlg.pp_mod_send.connect(self.pp_mod_send)
        dlg.exec()

    @QtCore.pyqtSlot(bool)
    def on_action_check_update(self, b):
        self.settings.setValue("check for updates", int(b))
        if b and self._update_thread is None:
            self._update_thread = QtCore.QThread()
            self._update_worker = update.UpdateWorker()
            self._update_worker.moveToThread(self._update_thread)
            self._update_worker.finished.connect(self._update_thread.quit)
            self._update_worker.data_ready.connect(
                self.on_action_check_update_finished)
            self._update_thread.start()

            ghrepo = "DC-analysis/DCscope"

            QtCore.QMetaObject.invokeMethod(
                self._update_worker,
                'processUpdate',
                QtCore.Qt.ConnectionType.QueuedConnection,
                QtCore.Q_ARG(str, version),
                QtCore.Q_ARG(str, ghrepo),
            )

    @QtCore.pyqtSlot(dict)
    def on_action_check_update_finished(self, mdict):
        # cleanup
        self._update_thread.quit()
        self._update_thread.wait()
        self._update_worker = None
        self._update_thread = None
        # display message box
        ver = mdict["version"]
        web = mdict["releases url"]
        dlb = mdict["binary url"]
        msg = QtWidgets.QMessageBox()
        msg.setWindowTitle("DCscope {} available!".format(ver))
        msg.setTextFormat(QtCore.Qt.TextFormat.RichText)
        text = "You can install DCscope {} ".format(ver)
        if dlb is not None:
            text += 'from a <a href="{}">direct download</a>. '.format(dlb)
        else:
            text += 'by running `pip install --upgrade dcscope`. '
        text += 'Visit the <a href="{}">official release page</a>!'.format(web)
        msg.setText(text)
        msg.exec()

    @QtCore.pyqtSlot()
    def on_action_compute_emodulus(self):
        dlg = bulk.BulkActionEmodulus(self, pipeline=self.pipeline)
        dlg.pp_mod_send.connect(self.pp_mod_send)
        dlg.exec()

    @QtCore.pyqtSlot()
    def on_action_compute_significance(self):
        # check that R is available
        if rsetup.has_r():
            dlg = compute.ComputeSignificance(self, pipeline=self.pipeline)
            dlg.exec()
        else:
            QtWidgets.QMessageBox.critical(
                self, "R not found!",
                "The R executable was not found. Please add it "
                + "to the PATH variable or define it manually in the "
                + "DCscope preferences.")

    @QtCore.pyqtSlot()
    def on_action_compute_statistics(self):
        dlg = compute.ComputeStatistics(self, pipeline=self.pipeline)
        dlg.exec()

    @QtCore.pyqtSlot()
    def on_action_clear(self):
        """Clear the entire session"""
        if bool(int(self.settings.value("advanced/user confirm clear", "1"))):
            button_reply = QtWidgets.QMessageBox.question(
                self, 'Clear Session', "All progress will be lost. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No)
            yes = button_reply == QtWidgets.QMessageBox.StandardButton.Yes
        else:
            yes = True
        if yes:
            with self.pipeline.lock:
                session.clear_session(self.pipeline)
                self.pp_mod_send.emit({"pipeline": {"cleared": "full"}})
            self.setWindowTitle(f"DCscope {version}")
        return yes

    @QtCore.pyqtSlot()
    def on_action_clear_datasets(self):
        """Clear only the datasets"""
        if bool(int(self.settings.value("advanced/user confirm clear", "1"))):
            button_reply = QtWidgets.QMessageBox.question(
                self, 'Clear Datasets',
                "Remove all datasets from this session?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No)
            yes = button_reply == QtWidgets.QMessageBox.StandardButton.Yes
        else:
            yes = True
        if yes:
            with self.pipeline.lock:
                slot_ids = list(self.pipeline.slot_ids)
                for slot_id in slot_ids:
                    self.pipeline.remove_slot(slot_id)
                self.pp_mod_send.emit(
                    {"pipeline": {"slots_removed": slot_ids}})
        return yes

    @QtCore.pyqtSlot()
    def on_action_dcor(self):
        """Show the DCOR import dialog"""
        dlg = dcor.DCORLoader(self)
        dlg.exec()

    @QtCore.pyqtSlot()
    def on_action_docs(self):
        webbrowser.open("https://dcscope.readthedocs.io")

    @QtCore.pyqtSlot()
    def on_action_export_data(self):
        dlg = export.ExportData(self, pipeline=self.pipeline)
        if dlg.path is not None:  # user pressed cancel
            dlg.exec()

    @QtCore.pyqtSlot()
    def on_action_export_filter_pipeline(self):
        """Export the entire filter pipeline"""
        dlg = export.ExportFilter(self,
                                  pipeline=self.pipeline,
                                  file_format="sof")
        dlg.exec()
        return dlg  # for testing

    @QtCore.pyqtSlot()
    def on_action_export_filter_polygon(self, exec_dialog=True):
        """Export only polygon filters of the current pipeline"""
        dlg = export.ExportFilter(self,
                                  pipeline=self.pipeline,
                                  file_format="poly")
        dlg.exec()
        return dlg  # for testing

    @QtCore.pyqtSlot()
    def on_action_export_filter_ray_dataset(self):
        """Export the filter ray for each dataset to the dataset location"""
        #: dictionary with paths as keys and filter ID list as values
        filt_dict = {}
        #: paths that already exist (user will be asked to override)
        existing_paths = []
        #: keeps track of datasets that are loaded twice (will notify user)
        double_paths = []
        #: keeps track of DCOR data
        dcor_data = []
        for slot in self.pipeline.slots:
            if slot.format == "dcor":
                dcor_data.append(slot.path)
                continue
            ray_path = slot.path.with_suffix(".sof")
            if ray_path in filt_dict:
                double_paths.append(ray_path)
                continue
            if ray_path.exists():
                existing_paths.append(ray_path)
            filters = self.pipeline.get_filters_for_slot(slot.identifier)
            filt_dict[ray_path] = [ff.identifier for ff in filters]
        if dcor_data:
            QtWidgets.QMessageBox.warning(
                self,
                "Some datasets are DCOR data for which no filter rays ",
                "will be exported:\n\n"
                + "\n".join([str(p) for p in list(set(dcor_data))])
            )
        if double_paths:
            QtWidgets.QMessageBox.warning(
                self,
                "Same datasets loaded in different slots",
                "The following datasets are loaded twice. Only the first "
                + "filter ray will be saved:\n\n"
                + "\n".join([str(p) for p in list(set(double_paths))])
            )
        if existing_paths:
            resp = QtWidgets.QMessageBox.question(
                self,
                "Override existing files?",
                "The following files already exist, override?\n\n"
                + "\n".join([str(p) for p in existing_paths])
            )
            if resp:
                # if the user agrees, these files will be overridden
                existing_paths.clear()
        for path in filt_dict:
            if path in existing_paths:
                # not overriding this one
                continue
            else:
                session.export_filters(path, self.pipeline, filt_dict[path])

    @QtCore.pyqtSlot()
    def on_action_export_plot(self):
        dlg = export.ExportPlot(self, pipeline=self.pipeline)
        dlg.exec()

    @QtCore.pyqtSlot()
    def on_action_import_filter(self, path=None):
        """Import a filter from a .sof or .poly file

        Parameters
        ----------
        path: str or pathlib.Path
            path to the filter to impoert
        """
        if path is None:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, 'Select Filter', '', 'Filters formats (*.poly *.sof)')
        if path:
            with self.pipeline.lock:
                session.import_filters(path, self.pipeline)
                self.pp_mod_send.emit(
                    {"pipeline": {"filters_imported": str(path)}})

    @QtCore.pyqtSlot()
    def on_action_open(self, path=None):
        """Open a DCscope session"""
        if self.pipeline.slots or self.pipeline.filters:
            if not self.on_action_clear():
                return
        if path is None:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, 'Open session', '', 'DCscope session (*.so2)',
                'DCscope session (*.so2)',
                QtWidgets.QFileDialog.Option.DontUseNativeDialog)
        if path:
            with self.pipeline.lock:
                search_paths = []
                while True:
                    try:
                        with widgets.ShowWaitCursor():
                            session.open_session(path=path,
                                                 pipeline=self.pipeline,
                                                 search_paths=search_paths)
                    except session.DataFileNotFoundError as e:
                        missds = "\r".join([str(pp) for pp in e.missing_paths])
                        msg = QtWidgets.QMessageBox()
                        msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
                        msg.setText("Some datasets were not found! "
                                    + "Please specify a search location.")
                        msg.setWindowTitle(
                            f"Missing {len(e.missing_paths)} dataset(s)")
                        msg.setDetailedText("Missing files: \n\n" + missds)
                        msg.exec()
                        spath = QtWidgets.QFileDialog.getExistingDirectory(
                            self, 'Data search path')
                        if spath:
                            search_paths.append(spath)
                        else:
                            break
                    else:
                        break
                self.show()
                self.pp_mod_send.emit(
                    {"pipeline": {"session_opened": str(path)}})
            self.setWindowTitle(
                f"{pathlib.Path(path).name} [DCscope {version}]")

    @QtCore.pyqtSlot()
    def on_action_preferences(self):
        """Show the preferences dialog"""
        dlg = preferences.Preferences(self)
        dlg.setWindowTitle("DCscope Preferences")
        dlg.pp_mod_send.connect(self.pp_mod_send)
        dlg.exec()

    @QtCore.pyqtSlot()
    def on_action_save(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save session', '', 'DCscope session (*.so2)')
        if path:
            if not path.endswith(".so2"):
                path += ".so2"
            session.save_session(path, self.pipeline)
            self.setWindowTitle(
                f"{pathlib.Path(path).name} [DCscope {version}]")

    @QtCore.pyqtSlot()
    def on_action_software(self):
        libs = [dclab,
                h5py,
                numpy,
                pg,
                scipy,
                ]

        sw_text = f"DCscope {version}\n\n"
        sw_text += f"Python {sys.version}\n\n"
        sw_text += "Modules:\n"
        for lib in libs:
            sw_text += f"- {lib.__name__} {lib.__version__}\n"
        sw_text += f"- PyQt6 {QtCore.QT_VERSION_STR}\n"  # Extrawurst
        sw_text += "\n Breeze icon theme by the KDE Community (LGPL)."
        if hasattr(sys, 'frozen'):
            sw_text += "\nThis executable has been created using PyInstaller."
        QtWidgets.QMessageBox.information(self, "Software", sw_text)

    @QtCore.pyqtSlot(int)
    def on_remove_polygon_filter_from_pipeline(self, pf_id):
        """Remove a polygon filter from all filters in the pipeline"""
        for filt in self.pipeline.filters:
            if pf_id in filt.polylist:
                filt.polylist.remove(pf_id)

    @widgets.show_wait_cursor
    @QtCore.pyqtSlot()
    def on_block_matrix(self):
        """Show/hide data matrix (User clicked Data Matrix button)"""
        if self.toolButton_dm.isChecked():
            self.splitter.setSizes([200, 1000])
        else:
            self.splitter.setSizes([0, 1])
        # redraw
        self.splitter.update()
        self.mdiArea.update()

    @QtCore.pyqtSlot()
    def on_new_polygon_filter(self):
        if not self.pipeline.slots:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Icon.Critical)
            msg.setText("A dataset is required for creating a polygon filter!")
            msg.setWindowTitle("No dataset loaded")
            msg.exec()
        else:
            self.toolButton_quick_view.setChecked(True)
            if not self.widget_quick_view.current_pipeline_element:
                # select the first item in the pipeline
                self.pp_mod_send.emit({"quickview": {
                    "slot_index": 0,
                    "filt_index": 0,
                    "slot_id": self.pipeline.slot_ids[0],
                    "filt_id": self.pipeline.filter_ids[0],
                }})

            self.widget_quick_view.on_poly_create()
            # adjusts QuickView size correctly
            self.widget_quick_view.on_tool()

    @widgets.show_wait_cursor
    @QtCore.pyqtSlot(str)
    def on_modify_filter(self, filt_id):
        self.widget_ana_view.tabWidget.setCurrentWidget(
            self.widget_ana_view.tab_filter)
        self.widget_ana_view.widget_filter.show_filter(filt_id)
        # finally, check the button
        self.toolButton_ana_view.setChecked(True)
        self.subwindows["analysis_view"].setVisible(True)
        # redraw
        self.mdiArea.update()
        self.subwindows["analysis_view"].update()

    @widgets.show_wait_cursor
    @QtCore.pyqtSlot(str)
    def on_modify_plot(self, plot_id):
        self.widget_ana_view.tabWidget.setCurrentWidget(
            self.widget_ana_view.tab_plot)
        self.widget_ana_view.widget_plot.show_plot(plot_id)
        # finally, check the button
        self.toolButton_ana_view.setChecked(True)
        self.subwindows["analysis_view"].setVisible(True)
        # redraw
        self.mdiArea.update()
        self.subwindows["analysis_view"].update()

    @widgets.show_wait_cursor
    @QtCore.pyqtSlot(str)
    def on_modify_slot(self, slot_id):
        self.widget_ana_view.tabWidget.setCurrentWidget(
            self.widget_ana_view.tab_slot)
        self.widget_ana_view.widget_slot.show_slot(slot_id)
        # finally, check the button
        self.toolButton_ana_view.setChecked(True)
        self.subwindows["analysis_view"].setVisible(True)
        # redraw
        self.mdiArea.update()
        self.subwindows["analysis_view"].update()

    @QtCore.pyqtSlot(dict)
    def on_pp_mod_recv(self, data):
        """Log modification information and send them on their way"""
        # Log all signals
        for key in data:
            logger.info(f"Signal '{key}': {json.dumps(data[key])}")

        if data.get("pipeline"):
            # Create plot windows
            plot_ids = self.pipeline.plot_ids
            for plot_id in plot_ids:
                self.add_plot_window(plot_id)

            # Remove zombie plot windows
            for plot_id_sw in list(self.subwindows_plots.keys()):
                if plot_id_sw not in plot_ids:
                    sub = self.subwindows_plots.pop(plot_id_sw)
                    for child in sub.children():
                        # disconnect signals
                        if isinstance(child, pipeline_plot.PipelinePlot):
                            self.plots_changed.disconnect(child.update_content)
                            break
                    sub.deleteLater()

            # Dis/enable plot button
            if self.pipeline.slots:
                self.toolButton_new_plot.setEnabled(True)
            else:
                self.toolButton_new_plot.setEnabled(False)

        # Enable QuickView if relevant
        if data.get("quickview"):
            if not self.subwindows["quick_view"].isVisible():
                self.toolButton_quick_view.setChecked(True)
                self.subwindows["quick_view"].setVisible(True)

        # Send new signal to all receivers
        self.pp_mod_recv.emit(data)

        QtWidgets.QApplication.processEvents(
            QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 300)

        if data.get("pipeline"):
            # Update plots after updating block matrix
            with widgets.ShowWaitCursor():
                self.plots_changed.emit()

        # redraw
        self.mdiArea.update()
        self.subwindows["analysis_view"].update()

    @QtCore.pyqtSlot()
    def on_splitter(self):
        if self.splitter.sizes()[0] == 0:
            self.toolButton_dm.setChecked(False)
        else:
            self.toolButton_dm.setChecked(True)

    def set_pipeline(self):
        if self.pipeline is not None:
            raise ValueError("Pipeline can only be set once")
        self.pipeline = pipeline.Pipeline()

        self.block_matrix.set_pipeline(self.pipeline)
        self.widget_quick_view.set_pipeline(self.pipeline)
        self.widget_ana_view.set_pipeline(self.pipeline)


def excepthook(etype, value, trace):
    """
    Handler for all unhandled exceptions.

    :param `etype`: the exception type (`SyntaxError`,
        `ZeroDivisionError`, etc...);
    :type `etype`: `Exception`
    :param string `value`: the exception error message;
    :param string `trace`: the traceback header, if any (otherwise, it
        prints the standard Python header: ``Traceback (most recent
        call last)``.
    """
    vinfo = f"Unhandled exception in DCscope version {version}:\n"
    exc_long = "".join(
        [vinfo] + traceback.format_exception(etype, value, trace))
    exc_short = "".join(
        [vinfo] + traceback.format_exception(etype, value, trace, limit=3))

    logger.error(exc_long)

    errorbox = QtWidgets.QMessageBox()
    errorbox.setIcon(QtWidgets.QMessageBox.Icon.Critical)
    copy_button = QtWidgets.QPushButton('Copy message to clipboard and close')
    copy_button.clicked.connect(lambda: copy_text_to_clipboard(exc_long))
    errorbox.addButton(QtWidgets.QPushButton('Close'),
                       QtWidgets.QMessageBox.ButtonRole.YesRole)
    errorbox.addButton(copy_button, QtWidgets.QMessageBox.ButtonRole.NoRole)
    errorbox.setDetailedText(exc_long)
    errorbox.setText(exc_short)
    errorbox.exec()


def copy_text_to_clipboard(text):
    cb = QtWidgets.QApplication.clipboard()
    cb.clear()
    cb.setText(text)


# Make Ctr+C close the app
signal.signal(signal.SIGINT, signal.SIG_DFL)
# Display exception hook in separate dialog instead of crashing
sys.excepthook = excepthook
