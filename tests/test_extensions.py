"""Test extension capabilities"""
import pathlib
import shutil
import tempfile

import pytest

from dclab.rtdc_dataset import feat_anc_plugin
from shapeout2 import extensions


data_path = pathlib.Path(__file__).parent / "data"


@pytest.fixture(autouse=True)
def cleanup_plugin_features():
    """Fixture used to cleanup plugin feature tests"""
    # code run before the test
    pass
    # then the test is run
    yield
    # code run after the test
    # remove our test plugin examples
    feat_anc_plugin.remove_all_plugin_features()


def test_em_basic():
    tmpd = pathlib.Path(tempfile.mkdtemp(prefix="extension_"))
    assert len(list(tmpd.glob("*"))) == 0
    em = extensions.ExtensionManager(store_path=tmpd)
    em.import_extension_from_path(data_path / "ext_feat_anc_plugin_ca.py")
    assert len(list(tmpd.glob("*"))) == 1
    em.extension_set_enabled(0, False)
    assert len(list(tmpd.glob("*"))) == 2
    assert len(list(tmpd.glob("*.py"))) == 1
    assert len(list(tmpd.glob("*.py_disabled"))) == 1
    em.extension_remove(0)
    assert len(list(tmpd.glob("*"))) == 0


def test_em_get_or_bust_extension():
    tmpd = pathlib.Path(tempfile.mkdtemp(prefix="extension_"))
    assert len(list(tmpd.glob("*"))) == 0
    em = extensions.ExtensionManager(store_path=tmpd)
    em.import_extension_from_path(data_path / "ext_feat_anc_plugin_ca.py")
    ext = em.get_extension_or_bust(0)
    assert not ext.path.samefile(data_path / "ext_feat_anc_plugin_ca.py")


def test_em_getitem_type():
    tmpd = pathlib.Path(tempfile.mkdtemp(prefix="extension_"))
    em = extensions.ExtensionManager(store_path=tmpd)
    em.import_extension_from_path(data_path / "ext_feat_anc_plugin_ca.py")

    with pytest.raises(ValueError, match="Extension not in"):
        em["peter"]

    with pytest.raises(IndexError, match="list index out of range"):
        em[1]

    tmpd2 = pathlib.Path(tempfile.mkdtemp(prefix="extension_"))
    script = (data_path / "ext_feat_anc_plugin_ca.py").read_text()
    (tmpd2 / "test.py").write_text(script.replace("_area", "_area2"))
    ext_not_in_manager = extensions.Extension(tmpd2 / "test.py")
    with pytest.raises(ValueError, match="Extension not in"):
        em[ext_not_in_manager]


def test_em_iter():
    tmpd = pathlib.Path(tempfile.mkdtemp(prefix="extension_"))
    em = extensions.ExtensionManager(store_path=tmpd)
    em.import_extension_from_path(data_path / "ext_feat_anc_plugin_ca.py")

    exts = [ee for ee in em]
    assert len(exts) == 1
    assert len(em) == 1

    tmpd2 = pathlib.Path(tempfile.mkdtemp(prefix="extension_"))
    script = (data_path / "ext_feat_anc_plugin_ca.py").read_text()
    (tmpd2 / "test.py").write_text(script.replace("_area", "_area2"))
    em.import_extension_from_path(tmpd2 / "test.py")

    exts = [ee for ee in em]
    assert len(exts) == 2
    assert len(em) == 2


def test_em_load_from_store():
    tmpd = pathlib.Path(tempfile.mkdtemp(prefix="extension_"))
    em = extensions.ExtensionManager(store_path=tmpd)
    ex = em.import_extension_from_path(data_path / "ext_feat_anc_plugin_ca.py")
    ex.set_enabled(False)

    em2 = extensions.ExtensionManager(store_path=tmpd)
    assert len(em2) == 1
    assert ex in em2
    assert ex.hash in em2
    assert 0 not in em2, "sanity check"


@pytest.mark.parametrize("path_name", ["ext_feat_anc_plugin_ca.py"])
def test_ex_all_enabled(path_name):
    tmpd = pathlib.Path(tempfile.mkdtemp(prefix="extension_"))
    path_used = tmpd / path_name
    shutil.copy2(data_path / path_name, path_used)
    ex = extensions.Extension(path_used)
    assert ex.enabled
    ex.set_enabled(False)
    assert not ex.enabled


@pytest.mark.parametrize("path_name", ["ext_feat_anc_plugin_ca.py"])
def test_ex_all_loaded(path_name):
    tmpd = pathlib.Path(tempfile.mkdtemp(prefix="extension_"))
    path_used = tmpd / path_name
    shutil.copy2(data_path / path_name, path_used)
    ex = extensions.Extension(path_used)
    assert not ex.loaded
    ex.load()
    assert ex.loaded
    ex.unload()
    assert not ex.loaded
    ex.set_enabled(False)
    ex.load()
    assert ex.path_lock_disabled.exists()
    assert not ex.loaded
    ex.destroy()
    assert not ex.path.exists()
    assert not ex.path_lock_disabled.exists()


@pytest.mark.parametrize("path_name", ["ext_feat_anc_plugin_ca.py"])
def test_ex_all_loaded_2(path_name):
    tmpd = pathlib.Path(tempfile.mkdtemp(prefix="extension_"))
    path_used = tmpd / path_name
    shutil.copy2(data_path / path_name, path_used)
    ex = extensions.Extension(path_used)
    assert not ex.loaded
    ex.load()
    ex.set_enabled(False)
    assert not ex.loaded
    assert not ex.enabled
    ex.set_enabled(True)
    assert ex.loaded
    assert ex.enabled


@pytest.mark.parametrize("path_name", ["ext_feat_anc_plugin_ca.py"])
def test_ex_all_repr(path_name):
    tmpd = pathlib.Path(tempfile.mkdtemp(prefix="extension_"))
    path_used = tmpd / path_name
    shutil.copy2(data_path / path_name, path_used)
    ex = extensions.Extension(path_used)
    assert path_name in repr(ex)


def test_ex_plugin_description():
    path_name = "ext_feat_anc_plugin_ca.py"
    tmpd = pathlib.Path(tempfile.mkdtemp(prefix="extension_"))
    path_used = tmpd / path_name
    shutil.copy2(data_path / path_name, path_used)
    ex = extensions.Extension(path_used)
    ex.load()
    assert "longer description" in ex.description


def test_ex_plugin_title():
    path_name = "ext_feat_anc_plugin_ca.py"
    tmpd = pathlib.Path(tempfile.mkdtemp(prefix="extension_"))
    path_used = tmpd / path_name
    shutil.copy2(data_path / path_name, path_used)
    ex = extensions.Extension(path_used)
    ex.load()
    assert "0.1.0" in ex.title
    assert "some circularity" in ex.title
