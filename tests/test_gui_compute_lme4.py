"""Test lme4 functionality"""
import pathlib
import socket

from dclab.lme4 import rsetup
from shapeout2.gui.main import ShapeOut2
from shapeout2 import session
from shapeout2.gui.compute.comp_lme4 import ComputeSignificance
import pytest


if not (rsetup.has_r() and rsetup.has_lme4()):
    pytest.skip(allow_module_level=True)

data_path = pathlib.Path(__file__).parent / "data"
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    try:
        s.connect(("www.python.org", 80))
        NET_AVAILABLE = True
    except socket.gaierror:
        # no internet
        NET_AVAILABLE = False


@pytest.fixture(autouse=True)
def run_around_tests():
    # Code that will run before your test, for example:
    session.clear_session()
    # A test function will be run at this point
    yield
    # Code that will run after your test, for example:
    session.clear_session()


@pytest.mark.skipif(not NET_AVAILABLE, reason="No network connection!")
@pytest.mark.filterwarnings(
    'ignore::dclab.rtdc_dataset.config.WrongConfigurationTypeWarning')
def test_lme4_with_dcor_session(qtbot):
    """
    Open a session with DCOR data and perform lme4 analysis from
    dclab docs at
    https://dclab.readthedocs.io/en/stable/sec_av_lme4.html
    """
    mw = ShapeOut2()
    qtbot.addWidget(mw)
    mw.on_action_open(data_path / "version_2_5_0_dcor_lme4.so2")

    # create dialog manually
    dlg = ComputeSignificance(mw, pipeline=mw.pipeline)

    # set the variables
    # treatment rep 1
    dlg.datasets[0].comboBox_group.setCurrentIndex(1)
    # treatment rep 2
    dlg.datasets[1].comboBox_group.setCurrentIndex(1)
    dlg.datasets[1].spinBox_repeat.setValue(2)
    # control rep 1
    pass
    # control rep 2
    dlg.datasets[3].spinBox_repeat.setValue(2)
    # control rep 3
    dlg.datasets[4].spinBox_repeat.setValue(3)

    # set the feature
    feat_id = dlg.comboBox_feat.findData("deform")
    dlg.comboBox_feat.setCurrentIndex(feat_id)

    dlgr = dlg.on_lme4(ret_dlg=True)

    assert dlgr.label_model.text() == "lmer"
    assert dlgr.label_feature.text() == "Deformation"
    assert dlgr.label_differential.text() == "No"
    assert dlgr.lineEdit_pvalue.text() == "0.012558"


@pytest.mark.skipif(not NET_AVAILABLE, reason="No network connection!")
@pytest.mark.filterwarnings(
    'ignore::dclab.rtdc_dataset.config.WrongConfigurationTypeWarning')
def test_lme4_with_dcor_session_differential(qtbot):
    """
    Perform differential deformation test
    """
    mw = ShapeOut2()
    qtbot.addWidget(mw)
    mw.on_action_open(data_path / "version_2_5_0_dcor_lme4_diff.so2")

    # create dialog manually
    dlg = ComputeSignificance(mw, pipeline=mw.pipeline)

    # set the variables
    # treatment rep 1
    dlg.datasets[0].comboBox_group.setCurrentIndex(1)
    # treatment rep 2
    dlg.datasets[1].comboBox_group.setCurrentIndex(1)
    dlg.datasets[1].spinBox_repeat.setValue(2)
    # res treatment rep 1
    dlg.datasets[2].comboBox_group.setCurrentIndex(1)
    # res treatment rep 2
    dlg.datasets[3].comboBox_group.setCurrentIndex(1)
    dlg.datasets[3].spinBox_repeat.setValue(2)
    # control rep 1
    pass
    # control rep 2
    dlg.datasets[5].spinBox_repeat.setValue(2)
    # control rep 3
    dlg.datasets[6].spinBox_repeat.setValue(3)
    # res control rep 1
    pass
    # res control rep 2
    dlg.datasets[8].spinBox_repeat.setValue(2)
    # res control rep 3
    dlg.datasets[9].spinBox_repeat.setValue(3)

    # set the feature
    feat_id = dlg.comboBox_feat.findData("deform")
    dlg.comboBox_feat.setCurrentIndex(feat_id)

    dlgr = dlg.on_lme4(ret_dlg=True)

    assert dlgr.label_model.text() == "lmer"
    assert dlgr.label_feature.text() == "Deformation"
    assert dlgr.label_differential.text() == "Yes"
    assert dlgr.lineEdit_pvalue.text() == "0.0000035055"
    assert dlgr.lineEdit_intercept.text() == "0.020509"
    assert dlgr.lineEdit_treatment.text() == "-0.0052991"
