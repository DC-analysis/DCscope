import importlib.resources
import traceback as tb
import urllib.parse
import webbrowser

import dclab
from PyQt6 import uic, QtCore, QtGui, QtWidgets
import requests

from ..widgets import show_wait_cursor, run_async


class DCORLoader(QtWidgets.QDialog):
    search_finished = QtCore.pyqtSignal(int, list, list, object)
    search_item_retrieved = QtCore.pyqtSignal(int, int, dict, dict, str)

    def __init__(self, parent, *args, **kwargs):
        """Search and load DCOR data"""
        super(DCORLoader, self).__init__(parent=parent, *args, **kwargs)
        ref = importlib.resources.files("shapeout2.gui.dcor") / "dcor.ui"
        with importlib.resources.as_file(ref) as path_ui:
            uic.loadUi(path_ui, self)

        self.main_ui = parent
        self.search_results = []
        self.num_searches = 0

        # Update UI
        self.settings = QtCore.QSettings()

        # tool button
        self.pushButton_search.clicked.connect(self.on_search)
        searchicon = QtGui.QIcon.fromTheme("search")
        self.pushButton_search.setIcon(searchicon)
        self.pushButton_search.setDefault(True)
        self.buttonBox.buttons()[1].setDefault(False)
        self.buttonBox.buttons()[0].setDefault(False)
        self.lineEdit_search.setFocus()

        # search signals
        self.search_finished.connect(self.on_search_finished)
        self.search_item_retrieved.connect(self.on_search_add_result)

        # button signals
        btn_close = self.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Close)
        btn_close.clicked.connect(self.on_close)
        btn_close.setToolTip("Close this window")
        closeicon = QtGui.QIcon.fromTheme("dialog-close")
        btn_close.setIcon(closeicon)
        btn_open = self.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Apply)
        btn_open.clicked.connect(self.on_open)
        btn_open.setToolTip("Add selected resources to current session")
        btn_open.setText("Add to session")
        plusicon = QtGui.QIcon.fromTheme("list-add")
        btn_open.setIcon(plusicon)
        btn_help = self.buttonBox.button(
            QtWidgets.QDialogButtonBox.StandardButton.Help)
        btn_help.clicked.connect(self.on_help)
        btn_help.setToolTip("View DCOR Quick Guide online")
        helpicon = QtGui.QIcon.fromTheme("documentinfo")
        btn_help.setIcon(helpicon)

    def get_api_base_url(self):
        """Return the API url in the form https://dcor.mpl.mpg.de/api/3"""
        server = self.settings.value("dcor/servers", ["dcor.mpl.mpg.de"])[0]
        server = server.strip("/")  # remove leading/trailing slashes
        use_ssl = bool(int(self.settings.value("dcor/use ssl", 1)))
        # ready API
        proto = "https" if use_ssl else "http"
        base = f"{proto}://{server}/api/3"
        return base

    def get_api_headers(self):
        """Return the API headers (Authorization with API key)"""
        api_key = self.settings.value("dcor/api key", "")
        # Add this API Key to the known API keys (dclab)
        dclab.rtdc_dataset.fmt_dcor.api.APIHandler.add_api_key(api_key)

        if api_key:
            api_headers = {"Authorization": api_key}
        else:
            api_headers = {}
        return api_headers

    @QtCore.pyqtSlot()
    def on_close(self):
        """Close window"""
        self.close()

    @show_wait_cursor
    @QtCore.pyqtSlot()
    def on_open(self):
        """Add selected resources to the current session"""
        for ii in range(self.listWidget.count()):
            item = self.listWidget.item(ii)
            if item.isSelected():
                self.main_ui.add_dataslot(
                    paths=[self.search_results[ii]], is_dcor=True)

    @QtCore.pyqtSlot()
    def on_help(self):
        """Show Shape-Out 2 docs"""
        webbrowser.open(
            "https://shapeout2.readthedocs.io/en/stable/sec_qg_dcor.html")

    @run_async  # comment-out for debugging
    @show_wait_cursor
    @QtCore.pyqtSlot()
    def on_search(self):
        """Trigger a search given the current search settings

        Notes
        -----
        This function is run in a background thread to not block
        the user interface. While this function is running, the
        user may start a new search. For each search, the counter
        ``self.num_searches`` is incremented. After a search is
        complete, the current search id is checked against
        ``self.num_searches`` and only if they match are the
        results displayed in the UI.

        See Also
        --------
        on_search_add_result: called for every search result
        on_search_finished: called when search finishes
        """
        self.num_searches += 1
        this_search_id = self.num_searches

        api_base_url = self.get_api_base_url()
        api_headers = self.get_api_headers()

        # search string
        if self.comboBox_search.currentIndex() == 1:
            stype = "dataset"
        else:
            stype = "free"
        search_string = urllib.parse.quote(self.lineEdit_search.text())

        # perform search
        try:
            # Results are handled individually via the `search_item_retrieved`
            # event.
            results, failed = self.perform_search(
                search_string=search_string,
                search_type=stype,
                search_id=this_search_id,
                api_base_url=api_base_url,
                api_headers=api_headers,
            )
        except BaseException:
            results = []
            failed = []
            error = tb.format_exc(limit=2, chain=False)
        else:
            error = False
        self.search_finished.emit(this_search_id, results, failed, error)

    @QtCore.pyqtSlot(int, int, dict, dict, str)
    def on_search_add_result(self, search_id, result_index, dataset, resource,
                             api_base_url):
        """Add new item to ``self.listWidget`` and ``self.search_results``"""
        if search_id == self.num_searches:
            if result_index == 0:
                self.listWidget.clear()
                self.search_results.clear()
            name = "{}: {} <{}@{}>".format(
                dataset["title"],
                resource["name"],
                dataset["name"],
                dataset["organization"]["name"],
            )
            self.listWidget.addItem(name)
            ru = api_base_url + "/action/dcserv?id={}".format(resource["id"])
            self.search_results.append(ru)

    @QtCore.pyqtSlot(int, list, list, object)
    def on_search_finished(self, search_id, results, failed, error):
        """Finalize search

        Finalization includes:

        - clear ``self.listWidget`` if the search had no results
        - display messages about datasets that were not displayed
        - display error messages
        """
        if search_id != self.num_searches:
            # user triggered next search
            return
        elif not results:
            # no results for this search
            self.listWidget.clear()

        if failed:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Information)
            msg.setText("Search found invalid data: {}".format(failed))
            msg.setWindowTitle("Dataset validation")
            msg.exec()

        if error:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Icon.Critical)
            msg.setText(error)
            msg.setWindowTitle("DCOR access error!")
            msg.exec()

    def perform_search(self, search_string, search_type, search_id,
                       api_base_url, api_headers):
        """Perform search

        Parameters
        ----------
        search_string: str
            Search string (already parsed using urllib.parse.quote)
        search_type: str
            "free": free text search
            or "dataset": resource/package name/id
        search_id: int
            Search identifier (must match `self.num_searches` for
            the search to continue)
        api_base_url: str
            Everything up until "https://server.example.org/api/3"
        api_headers: dict
            Headers for the request
        """
        if search_type == "free":
            url = api_base_url + "/action/package_search?q={}".format(
                search_string)
            # limit to 20 rows
            url += "&rows=20"
            # include private data
            url += "&include_private=True"
            urls = [url]
        else:
            urls = [
                api_base_url + "/action/package_show?id={}".format(
                    search_string),
                api_base_url + "/action/resource_show?id={}".format(
                    search_string),
            ]

        pkg_res = []
        for url in urls:
            req = requests.get(url,
                               headers=api_headers,
                               verify=get_server_cert_path())
            if not req.ok:
                continue
            resp = req.json()["result"]
            if "count" in resp and "results" in resp:
                # free search
                for pkg in resp["results"]:
                    if "resources" in pkg:
                        for res in pkg["resources"]:
                            pkg_res.append([pkg, res])
            elif "resources" in resp:
                # package show
                for res in resp["resources"]:
                    pkg_res.append([resp, res])
                break  # no additional search for resource
            else:
                # resource show
                purl = api_base_url + "/action/package_show?id={}".format(
                    resp["package_id"])
                pkg = requests.get(purl,
                                   headers=api_headers,
                                   verify=get_server_cert_path(),
                                   ).json()["result"]
                pkg_res.append([pkg, resp])
                break  # no additional search for package

        results = []
        failed = []
        for ii, (pkg, res) in enumerate(pkg_res):
            if res["mimetype"] not in ["RT-DC"]:
                continue  # only use RT-DC data
            if search_id != self.num_searches:
                break  # stop doing things in the background
            # check availability of each resource
            c = api_base_url + "/action/dcserv?id={}&query=valid".format(
                res["id"])
            req = requests.get(c,
                               headers=api_headers,
                               verify=get_server_cert_path())
            if req.ok and req.json()["result"]:  # only use valid data
                self.search_item_retrieved.emit(search_id, ii, pkg, res,
                                                api_base_url)
                results.append(res)
            else:
                failed.append("{}: {}".format(res["id"], req.reason))
        return results, failed


def get_server_cert_path(host=None):
    """Return server certificate for current DCOR server if available"""
    settings = QtCore.QSettings()
    if host is None:
        host = settings.value("dcor/servers", ["dcor.mpl.mpg.de"])[0]
        host = host.strip("/")  # remove leading/trailing slashes

    return dclab.rtdc_dataset.fmt_dcor.get_server_cert_path(host)
