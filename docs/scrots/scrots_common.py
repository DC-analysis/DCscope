"""Common setup for the documentation screenshots

- The datasets are part of the soRT-FDC manuscript data on figshare
  (https://doi.org/10.6084/m9.figshare.11302595.v1). Missing datasets
  are downloaded to this directory (and ignored by git).
- The icon theme and the "Fusion" style of DCscope are used (like in
  `dcscope/__main__.py`), so that the screenshots do not depend on the
  desktop environment.
"""
import hashlib
import importlib.resources
import pathlib
import urllib.request

from PyQt6 import QtGui, QtWidgets

HERE = pathlib.Path(__file__).parent

#: file name, figshare download URL, MD5 sum
DATASETS = [
    ("Figure3_Blood_Initial.rtdc",
     "https://ndownloader.figshare.com/files/20032163",
     "2f4d1d7fd5ba1a172b1f6dd89bd59eb9"),
    ("Figure3_Blood_Target_neuBr.rtdc",
     "https://ndownloader.figshare.com/files/20032166",
     "01ddd88e71232dd2e4c8d53483eeaac0"),
]


def md5sum(path):
    hasher = hashlib.md5()
    with path.open("rb") as fd:
        while chunk := fd.read(2**20):
            hasher.update(chunk)
    return hasher.hexdigest()


def download(url, path, md5):
    """Download `url` to `path` and verify the MD5 sum"""
    path_part = path.with_name(path.name + ".part")
    print(f"Downloading {path.name}...")
    # figshare redirects to a presigned URL (HEAD and range requests
    # are not allowed)
    req = urllib.request.Request(url, headers={"User-Agent": "Python"})
    with urllib.request.urlopen(req) as resp, path_part.open("wb") as fd:
        size = int(resp.headers.get("content-length", 0))
        done = 0
        while chunk := resp.read(2**20):
            fd.write(chunk)
            done += len(chunk)
            if size:
                print(f"\r  {done / size:.0%}", end="", flush=True)
    print()
    if md5sum(path_part) != md5:
        path_part.unlink()
        raise ValueError(f"MD5 sum mismatch for {path.name}!")
    path_part.rename(path)


def ensure_datasets():
    """Download all datasets that are not in this directory"""
    for name, url, md5 in DATASETS:
        path = HERE / name
        if not path.exists():
            download(url, path, md5)


def setup_style():
    """Use the "Fusion" style, like DCscope (see `dcscope/__main__.py`)

    Call this after creating the QApplication.
    """
    QtWidgets.QApplication.setStyle("Fusion")


def setup_icon_theme():
    """Use the (light) icon theme of DCscope

    Call this after creating the QApplication.
    """
    ref = importlib.resources.files("dcscope.img") / "icon.png"
    with importlib.resources.as_file(ref) as icon_path:
        theme_path = icon_path.with_name("icon-theme") / "light"
    QtGui.QIcon.setThemeSearchPaths([str(theme_path)])
    QtGui.QIcon.setThemeName(".")


if __name__ == "__main__":
    ensure_datasets()
