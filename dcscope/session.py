import hashlib
import io
import json
import os
import pathlib
import shutil
import tempfile
import zipfile

import dclab
from dclab.util import file_monitoring_lru_cache
import numpy as np

from .pipeline import Dataslot, Filter, Pipeline, Plot
from ._version import version


class DataFileNotFoundError(BaseException):
    def __init__(self, missing_paths, *args):
        self.missing_paths = missing_paths
        super(DataFileNotFoundError, self).__init__(*args)


class DCscopeSessionJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, pathlib.Path):
            return {"__type__": "path",
                    "__data__": o.as_posix()
                    }
        elif isinstance(o, np.floating):  # handle np.float32
            return float(o)

        # Let the base class default method raise the TypeError
        return super(DCscopeSessionJSONEncoder, self).default(o)


class PathlibJSONDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        super(PathlibJSONDecoder, self).__init__(object_hook=self.object_hook,
                                                 *args, **kwargs)

    @staticmethod
    def compat_2_5_1(obj):
        """New standard for emodulus computation keyword arguments

        This compatibility hook was introduced in DCscope.5.1
        and is used to convert [calculation]: "emodulus model" which
        was deprecated in dclab 0.32.0 to [calculation]: "emodulus lut".
        """
        if ("emodulus model" in obj
                and obj["emodulus model"] == "elastic sphere"):
            obj.pop("emodulus model")
            obj["emodulus lut"] = "LE-2D-FEM-19"

    def object_hook(self, obj):
        if "__type__" in obj and obj["__type__"] == "path":
            return pathlib.Path(obj["__data__"])
        self.compat_2_5_1(obj)
        return obj


def export_filters(path, pipeline, filt_ids=None):
    """Export filters of a pipeline to a JSON file"""
    if filt_ids is None:
        # export all filters
        filt_ids = pipeline.filter_ids
        # export all polygon filters as well
        # (also if they are not used by any of the filters)
        poly_ids = [pf.unique_id for pf in dclab.PolygonFilter.instances]
    else:
        # get all relevant polygon filters
        poly_ids = set([])
        for filt in pipeline.filters:
            if filt.identifier in filt_ids:
                poly_ids |= set(filt.polylist)

    poly_states = []
    for pid in sorted(poly_ids):
        pf = dclab.PolygonFilter.get_instance_from_id(pid)
        poly_states.append(pf.__getstate__())
    # Then, get the remaining filter settings
    filt_states = []
    for filt in pipeline.filters:
        if filt.identifier in filt_ids:
            filt_states.append(filt.__getstate__())
    state = {"polygon filters": poly_states,
             "filters": filt_states}
    dump = json.dumps(state, **JSON_DUMP_KWARGS)
    pathlib.Path(path).write_text(dump)


def import_filters(path: pathlib.Path | str,
                   pipeline: Pipeline,
                   strict: bool = False):
    """Load filters from a JSON file into a pipeline

    Parameters
    ----------
    path: pathlib.Path or str or io.IOBase
        Path to the filter file
    pipeline: dcscope.pipeline.Pipeline
        Analysis pipeline to import filters to
    strict: bool
        If False (default), new filter identifiers are created
        for each filter. If True, the given filter identifiers
        will be used - Raises a ValueError if the filter exists.
        For loading filters into a pipeline, this should be False.
        For loading session filters, this should be True.
        Has no effect when `path` is a .poly file.
    """
    if isinstance(path, io.IOBase):
        import_filter_set(path, pipeline, strict)
    else:
        path = pathlib.Path(path)
        if path.suffix == ".poly":
            # add a new polygon filter
            dclab.PolygonFilter.import_all(path)
        elif path.suffix == ".sof":
            import_filter_set(path, pipeline, strict)
        else:
            raise ValueError("Unrecognized file extension "
                             + "'{}' for filters.".format(path.suffix))


def import_filter_set(path, pipeline, strict=False):
    """Import a filter set

    See :func:`import_filters`
    """
    if isinstance(path, io.IOBase):
        dump = path.read()
    else:
        dump = path.read_text()
    dump_state = json.loads(dump)
    # add polygon filters from file
    if not strict:
        pf_dict = {}  # maps old to new identifiers
    for pstate in dump_state["polygon filters"]:
        pf = dclab.PolygonFilter(axes=(pstate["axis x"], pstate["axis y"]),
                                 points=pstate["points"])
        pid = pstate["identifier"]
        if not strict:
            # keep track of old and new identifiers
            pf_dict[pid] = pf.unique_id
        if pid != pf.unique_id:
            if strict:
                if dclab.PolygonFilter.unique_id_exists(pid):
                    raise ValueError("PolygonFilter with unique_id "
                                     + "{} already exists!".format(pid))
                else:
                    # change the unique_id to that of the original filter
                    pf._set_unique_id(pid)
            else:
                # use the unique_id of the newly-created filter
                pstate["identifier"] = pf.unique_id
        pf.__setstate__(pstate)
    # add a new filter set
    for state in dump_state["filters"]:
        if strict:
            filt = Filter(identifier=state["identifier"])
        else:
            filt = Filter()
            state["identifier"] = filt.identifier
            # transform original polygon filter ids
            newpids = [pf_dict[pid] for pid in state["polygon filters"]]
            state["polygon filters"] = newpids
        filt.__setstate__(state)
        pipeline.add_filter(filt=filt)


@file_monitoring_lru_cache(maxsize=1000)
def hash_file_partially(path, size=524288):
    """Hash parts of a file for basic identification

    By default, the first and final 512kB are hashed.
    """
    fsize = path.stat().st_size
    size = min(size, fsize)
    with path.open("rb") as fd:
        head = fd.read(size)
        fd.seek(fsize-size)
        tail = fd.read(size)
        hexhash = hashlib.md5(head + tail).hexdigest()
    return hexhash


def save_session(path, pipeline):
    """Save an entire pipeline session"""
    path = pathlib.Path(path)
    tempdir = pathlib.Path(tempfile.mkdtemp(prefix="DCscope-session-save_"))
    # filters
    export_filters(tempdir / "filters.sof", pipeline)
    # slots
    for ii, slot in enumerate(pipeline.slots):
        sdump = json.dumps(slot.__getstate__(), **JSON_DUMP_KWARGS)
        (tempdir / "slot_{}.json".format(ii)).write_text(sdump)
    # plots
    for jj, plot in enumerate(pipeline.plots):
        pdump = json.dumps(plot.__getstate__(), **JSON_DUMP_KWARGS)
        (tempdir / "plot_{}.json".format(jj)).write_text(pdump)
    # pipeline block matrix
    mdump = json.dumps(pipeline.element_states, **JSON_DUMP_KWARGS)
    (tempdir / "matrix.json").write_text(mdump)
    # additional information
    search_paths = {}
    dataset_hashes = {}
    dataset_formats = {}
    for slot in pipeline.slots:
        # format (hdf5 or dcor)
        dataset_formats[slot.identifier] = slot.format
        if slot.format == "hdf5":
            # search path
            try:
                rel = os.path.relpath(slot.path.parent, path.parent)
            except (OSError, ValueError):
                rel = "."
            search_paths[slot.identifier] = rel
            # file hash
            hash_size = 48128
            dataset_hashes[slot.identifier] = {
                # these are keyword arguments to find_file
                "partial_hash": hash_file_partially(slot.path, size=hash_size),
                "size_read": hash_size
            }
    remarks = {"search paths": search_paths,
               "file hashes": dataset_hashes,
               "formats": dataset_formats,
               "version": version,
               }
    rdump = json.dumps(remarks, **JSON_DUMP_KWARGS)
    (tempdir / "remarks.json").write_text(rdump)
    # zip everything
    with zipfile.ZipFile(path, mode='w') as arc:
        for pp in tempdir.rglob("*"):
            if pp.is_file():
                arc.write(pp, pp.relative_to(tempdir))
    # cleanup
    shutil.rmtree(str(tempdir), ignore_errors=True)


def clear_session(pipeline=None):
    """Clear the entire analysis pipeline"""
    if pipeline is not None:
        # reset the pipeline
        pipeline.reset()
    # remove any existing filters, plots, or slots and reset their counters
    for cls in [Dataslot, Filter, Plot]:
        cls._instance_counter = 0
        cls._instances = {}
    # remove polygon filters
    dclab.PolygonFilter.clear_all_filters()


def find_file(original_path, search_paths, partial_hash, size_read):
    """Find a file

    Parameters
    ----------
    original_path: pathlib.Path
        The original path to the file
    search_paths: list
        Directories or possible candidates for the file. In
        directories, only files with the same name are searched.
    partial_hash: str
        Hash of the file, see :func:`hash_file_partially`

    Returns a pathlib.Path object on success, False otherwise.
    """
    search_paths = [pathlib.Path(sp) for sp in search_paths]
    if original_path.exists():
        # we boldly assume that the hash matches
        path = original_path
    else:
        for pp in search_paths:
            if pp.is_dir():
                # look in the directory
                newp = pp / original_path.name
                if newp.exists():
                    newh = hash_file_partially(newp, size=size_read)
                    if newh == partial_hash:
                        path = newp
                        break
            elif pp.exists():
                # maybe this is the file?
                newh = hash_file_partially(pp, size=size_read)
                if newh == partial_hash:
                    path = pp
                    break
        else:
            path = False
    return path


def open_session(path, pipeline=None, search_paths=None):
    """Load a session (optionally overriding an existing pipeline)

    Parameters
    ----------
    path: pathlib.Path or str
        Path to the session file
    pipeline: dcscope.pipeline.Pipeline or None
        If a pipeline is given, it is reset before loading anything
    search_paths: list
        Paths to search for missing measurements; entries may be
        directories or .rtdc files
    """
    if search_paths is None:
        search_paths = []
    path = pathlib.Path(path)
    if pipeline is None:
        pipeline = Pipeline()
    clear_session(pipeline)
    # read data directly from the zip file
    with zipfile.ZipFile(path, mode='r') as arc:
        # remarks
        remarks = json.loads(arc.read("remarks.json"))
        # determine dataset paths from slot states
        slotnames = sorted(
            [n for n in arc.namelist() if n.startswith("slot_")],
            key=lambda x: int(x[5:-5]))  # by index
        slot_states = []
        missing_paths = []
        for sn in slotnames:
            sstate = json.loads(arc.read(sn), cls=PathlibJSONDecoder)
            slot_id = sstate["identifier"]
            # "formats" was added in 2.1.0 (when dcor format was added)
            ishdf5 = ("formats" not in remarks
                      or remarks["formats"][slot_id] == "hdf5")
            if ishdf5:
                # also search relative paths
                search_ap = path.parent / remarks["search paths"][slot_id]
                newpath = find_file(original_path=sstate["path"],
                                    search_paths=search_paths + [search_ap],
                                    **remarks["file hashes"][slot_id])
                if newpath:
                    sstate["path"] = newpath
                    slot_states.append(sstate)
                else:
                    missing_paths.append(sstate["path"])
            else:
                slot_states.append(sstate)
        # raise an exception if data files are missing
        if missing_paths:
            # Which files are missing is stored as a property in the exception.
            # By catching this exception, a GUI can request the user to select
            # a search directory and try again.
            raise DataFileNotFoundError(
                missing_paths,
                "Some files are missing! You can access them via the "
                + "`missing_paths` property of this exception.")
        # load filters
        import_filters(arc.open("filters.sof"), pipeline, strict=True)
        # load slots
        for sstate in slot_states:
            pipeline.add_slot(sstate)
        # load plots
        plotnames = sorted(
            [n for n in arc.namelist() if n.startswith("plot_")],
            key=lambda x: int(x[5:-5]))  # by index
        for pn in plotnames:
            pstate = json.loads(arc.read(pn))
            pipeline.add_plot(pstate)
        # load element states
        estates = json.loads(arc.read("matrix.json"))
        pipeline.element_states = estates
    return pipeline


JSON_DUMP_KWARGS = {
    "cls": DCscopeSessionJSONEncoder,
    "sort_keys": True,
    "indent": 2,
}
