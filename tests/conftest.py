import shutil
import tempfile
import time

from PyQt6 import QtCore
import pytest

from dcscope.gui.main import DCscope


TMPDIR = tempfile.mkdtemp(prefix=time.strftime(
    "dcscope_test_%H.%M_"))

pytest_plugins = ["pytest-qt"]


@pytest.fixture
def mw():
    mw = DCscope()
    yield mw
    mw.close()


def pytest_configure(config):
    """This is ran before all tests"""
    # disable update checking
    QtCore.QCoreApplication.setOrganizationName("DC-analysis")
    QtCore.QCoreApplication.setOrganizationDomain("dc-cosmos.org")
    QtCore.QCoreApplication.setApplicationName("dcscope")
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
    settings = QtCore.QSettings()
    settings.setValue("check for updates", 0)
    settings.setValue("advanced/user confirm clear", 0)
    settings.sync()
    # set global temp directory
    tempfile.tempdir = TMPDIR


def pytest_unconfigure(config):
    """
    called before test process is exited.
    """
    QtCore.QCoreApplication.setOrganizationName("DC-analysis")
    QtCore.QCoreApplication.setOrganizationDomain("dc-cosmos.org")
    QtCore.QCoreApplication.setApplicationName("dcscope")
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
    settings = QtCore.QSettings()
    settings.setValue("advanced/user confirm clear", 1)
    # clear global temp directory
    shutil.rmtree(TMPDIR, ignore_errors=True)
