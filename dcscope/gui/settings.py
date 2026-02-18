import pathlib
from PyQt6 import QtCore


def get_dir(topic: str,
            settings: QtCore.QSettings
            ) -> str:
    """Given a QSettings instance, return a directory

    If writable is `True`, return a writable directory
    """
    location = settings.value(f"paths/{topic}", "")

    if not location:
        # use default value
        location = QtCore.QStandardPaths.standardLocations(
            QtCore.QStandardPaths.StandardLocation.HomeLocation)[0]
    else:
        # check whether the location exists
        path = pathlib.Path(location)
        if not path.is_dir():
            for pp in path.parents:
                if pp.is_dir():
                    location = str(pp)
                    break
            else:
                location = "."

    return location or "."


def set_dir(topic: str,
            path: pathlib.Path | str,
            settings: QtCore.QSettings,
            ):
    """Given a QSettings instance, save a directory topic"""
    path = pathlib.Path(path)
    if path.exists():
        if not path.is_dir():
            path = path.parent
        settings.setValue(f"paths/{topic}", str(path))
