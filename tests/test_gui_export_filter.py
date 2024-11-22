import pathlib
import shutil
import tempfile

import dclab
import numpy as np
from PyQt6 import QtCore, QtWidgets

import pytest

from shapeout2.gui.main import ShapeOut2
from shapeout2.gui.export.e2filter import ExportFilter

data_path = pathlib.Path(__file__).parent / "data"


@pytest.fixture(autouse=True)
def run_around_tests():
    dclab.PolygonFilter.clear_all_filters()
    yield
    dclab.PolygonFilter.clear_all_filters()


def test_gui_export_filter_ray(qtbot, monkeypatch):
    tdir = tempfile.mkdtemp()
    path = pathlib.Path(tdir) / "data.rtdc"
    shutil.copy2(data_path / "calibration_beads_47.rtdc", path)
    # create a polygon filter
    with dclab.new_dataset(path) as ds:
        pf1 = dclab.PolygonFilter(
            axes=("deform", "area_um"),
            points=[[np.min(ds["deform"]), np.min(ds["area_um"])],
                    [np.min(ds["deform"]), np.mean(ds["area_um"])],
                    [np.mean(ds["deform"]), np.mean(ds["area_um"])],
                    ],
            name="Triangle of Death",
        )

    mw = ShapeOut2()
    qtbot.addWidget(mw)
    mw.add_dataslot(paths=[path])

    # enable the filter
    slot_id = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em = mw.block_matrix.get_widget(slot_id, filt_id)
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton)
    # did that work?
    assert mw.pipeline.is_element_active(slot_id, filt_id)
    assert len(mw.pipeline.slot_ids) == 1, "we added that"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # enable the polygon filter
    wf = mw.widget_ana_view.widget_filter
    wf._polygon_checkboxes[pf1.unique_id].setChecked(True)
    assert wf._polygon_checkboxes[pf1.unique_id].isChecked()

    # click apply
    qtbot.mouseClick(wf.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)

    # check the filter
    assert pf1.unique_id in mw.pipeline.filters[0].polylist

    # disable "exec"
    monkeypatch.setattr(ExportFilter, "exec", lambda *args: None)

    # export the filter ray
    mw.on_action_export_filter_ray_dataset()
    sof_out = path.with_suffix(".sof")
    assert sof_out.exists()


def test_gui_export_polygon_filters(qtbot, monkeypatch):
    path = data_path / "calibration_beads_47.rtdc"
    # create a polygon filter
    with dclab.new_dataset(path) as ds:
        pf1 = dclab.PolygonFilter(
            axes=("deform", "area_um"),
            points=[[np.min(ds["deform"]), np.min(ds["area_um"])],
                    [np.min(ds["deform"]), np.mean(ds["area_um"])],
                    [np.mean(ds["deform"]), np.mean(ds["area_um"])],
                    ],
            name="Triangle of Death",
        )
        pf2 = dclab.PolygonFilter(
            axes=("deform", "area_um"),
            points=[[np.min(ds["deform"]), np.min(ds["area_um"])],
                    [np.max(ds["deform"]), np.mean(ds["area_um"])],
                    [np.mean(ds["deform"]), np.mean(ds["area_um"])],
                    ],
            name="Second Triangle of Death",
        )

    mw = ShapeOut2()
    qtbot.addWidget(mw)
    mw.add_dataslot(paths=[path])

    # enable the filter
    slot_id = mw.pipeline.slot_ids[0]
    filt_id = mw.pipeline.filter_ids[0]
    em = mw.block_matrix.get_widget(slot_id, filt_id)
    qtbot.mouseClick(em, QtCore.Qt.MouseButton.LeftButton)
    # did that work?
    assert mw.pipeline.is_element_active(slot_id, filt_id)
    assert len(mw.pipeline.slot_ids) == 1, "we added that"
    assert len(mw.pipeline.filter_ids) == 1, "automatically added"

    # enable the polygon filter
    wf = mw.widget_ana_view.widget_filter
    filter_ids = list(wf._polygon_checkboxes.keys())
    # sanity check
    assert filter_ids == [pf1.unique_id, pf2.unique_id]

    wf._polygon_checkboxes[pf1.unique_id].setChecked(True)
    wf._polygon_checkboxes[pf2.unique_id].setChecked(True)
    assert wf._polygon_checkboxes[pf1.unique_id].isChecked()
    assert wf._polygon_checkboxes[pf2.unique_id].isChecked()

    # click apply
    qtbot.mouseClick(wf.pushButton_apply, QtCore.Qt.MouseButton.LeftButton)

    # check the filter
    assert pf1.unique_id in mw.pipeline.filters[0].polylist
    assert pf2.unique_id in mw.pipeline.filters[0].polylist

    # disable "exec"
    monkeypatch.setattr(ExportFilter, "exec", lambda *args: None)

    # export the polygon filter
    dlg = mw.on_action_export_filter_polygon()
    assert dlg.file_format == "poly"

    qtbot.mouseClick(dlg.radioButton_multiple,
                     QtCore.Qt.MouseButton.LeftButton)
    assert dlg.file_mode == "multiple"

    # set directory
    tdir = tempfile.mkdtemp()
    monkeypatch.setattr(QtWidgets.QFileDialog,
                        "getExistingDirectory",
                        lambda *args: tdir)
    dlg.done(True)

    # check that there are two files
    paths = list(pathlib.Path(tdir).glob("*.poly"))
    assert len(paths) == 2

    # load the filters
    pl1 = dclab.PolygonFilter(filename=paths[0], unique_id=3)
    pl2 = dclab.PolygonFilter(filename=paths[1], unique_id=4)

    # ordering of files not well-defined
    if pl1 == pf1:
        assert pl2 == pf2
    elif pl1 == pf2:
        assert pl2 == pf1
    else:
        assert False
