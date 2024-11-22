import copy
import warnings

import dclab
import numpy as np

from ..idiom import SLOPING_FEATURES

from .dataslot import Dataslot
from .filter import Filter
from .filter_ray import FilterRay
from .plot import Plot


class EmptyDatasetWarning(UserWarning):
    pass


class MissingFeatureWarning(UserWarning):
    pass


class Pipeline(object):
    def __init__(self, state=None):
        #: Filters are instances of :class:`shapeout2.pipeline.Filter`
        self.filters = []
        #: Plots are instances of :class:`shapeout2.pipeline.Plot`
        self.plots = []
        #: Filter rays of the current pipeline
        self.rays = {}
        #: Slots are instances of :class:`shapeout2.pipeline.Dataslot`
        self.slots = []
        #: individual element states
        self.element_states = {}

        self.reset()
        #: previous state (see __setstate__)
        self._old_state = {}
        if state is not None:
            self.__setstate__(state)

    def __setstate__(self, state):
        if self._old_state == state:
            # Nothing changed
            return
        self._old_state = state
        self.reset()
        for filt_state in state["filters"]:
            self.add_filter(filt_state)
        for plot_state in state["plots"]:
            self.add_plot(plot_state)
            self.check_contour_spacing(plot_state["identifier"])
        for slot_state in state["slots"]:
            self.add_slot(slot=slot_state)
        # set element states at the end
        self.element_states = state["elements"]

        # sanity checks
        if set(self.filters_used) != set(state["filters used"]):
            raise ValueError("Bad pipeline state ('filters used' don't match)")
        if set(self.slots_used) != set(state["slots used"]):
            raise ValueError("Bad pipeline state ('slots used' don't match)")

    def __getstate__(self):
        state = {"elements": copy.deepcopy(self.element_states),
                 "filters": [filt.__getstate__() for filt in self.filters],
                 "filters used": self.filters_used,
                 "plots": [plot.__getstate__() for plot in self.plots],
                 "slots": [slot.__getstate__() for slot in self.slots],
                 "slots used": self.slots_used}
        return state

    @property
    def filter_ids(self):
        return [filt.identifier for filt in self.filters]

    @property
    def filters_used(self):
        return [filt.identifier for filt in self.filters if filt.filter_used]

    @property
    def plot_ids(self):
        return [plot.identifier for plot in self.plots]

    @property
    def slot_ids(self):
        return [slot.identifier for slot in self.slots]

    @property
    def slots_used(self):
        return [slot.identifier for slot in self.slots if slot.slot_used]

    @property
    def num_filters(self):
        return len(self.filters)

    @property
    def num_plots(self):
        return len(self.plots)

    @property
    def num_slots(self):
        return len(self.slots)

    @property
    def paths(self):
        return [ds.path for ds in self.slots]

    def add_filter(self, filt=None, index=None):
        """Add a filter to the pipeline

        Parameters
        ----------
        filt: shapeout2.pipeline.Filter or dict
            Filter instance or its state from Filter.__getstate__()
        index: int
            Position in the filter list, defaults to `len(self.filters)`

        Returns
        -------
        index: int
            index of the filter in the pipeline;
            indexing starts at "0".
        """
        if index is None:
            index = self.num_filters
        if filt is None:
            filt = Filter()
        elif isinstance(filt, Filter):
            pass
        elif isinstance(filt, dict):
            state = filt
            if state["identifier"] in Filter._instances:
                filt = Filter._instances[filt["identifier"]]
            else:
                filt = Filter()
            filt.__setstate__(state)
        self.filters.insert(index, filt)
        filt_id = filt.identifier
        for slot_id in self.slot_ids:
            self.element_states[slot_id][filt_id] = False
        return filt_id

    def add_plot(self, plot=None, index=None):
        """Add a plot to the pipeline

        Parameters
        ----------
        plot: shapeout2.pipeline.Plot or dict
            Plot instance or its state from Plot.__getstate__()
        index: int
            Position in the plot list, defaults to `len(self.plots)`

        Returns
        -------
        index: int
            index of the plot in the pipeline;
            indexing starts at "0".
        """
        if index is None:
            index = self.num_plots
        if plot is None:
            plot = Plot()
        elif isinstance(plot, Plot):
            pass
        elif isinstance(plot, dict):
            state = plot
            if state["identifier"] in Plot._instances:
                plot = Plot._instances[plot["identifier"]]
            else:
                plot = Plot()
            plot.__setstate__(state)

        self.plots.insert(index, plot)
        plot_id = plot.identifier
        for slot_id in self.slot_ids:
            self.element_states[slot_id][plot_id] = False

        return plot.identifier

    def add_slot(self, slot=None, path=None, index=None):
        """Add a slot (experiment) to the pipeline

        Parameters
        ----------
        slot: shapeout2.pipeline.Dataslot or dict
            Dataslot representing an experimental dataset or its
            state from Dataslot.__getstate__(); At least `slot`
            or `path` need to be specified
        path: str or pathlib.Path
            Path to a measurement or DCOR URL
        index: int
            Position in the slot list, defaults to `len(self.slots)`

        Returns
        -------
        index: int
            index of the slot in the pipeline;
            indexing starts at "0".
        identifier: str
            identifier of the slot
        """
        if index is None:
            index = self.num_slots
        if ((slot is None and path is None)
                or (slot is not None and path is not None)):
            raise ValueError("Please specify either `slot` or `path`.")
        elif path is not None:
            slot = Dataslot(path=path)
        elif isinstance(slot, Dataslot):
            pass
        elif isinstance(slot, dict):
            state = slot
            if state["identifier"] in Dataslot._instances:
                slot = Dataslot._instances[slot["identifier"]]
            else:
                slot = Dataslot()
            slot.__setstate__(state)

        self.slots.insert(index, slot)
        slot_id = slot.identifier
        self.element_states[slot_id] = {}
        for filt_id in self.filter_ids:
            self.element_states[slot_id][filt_id] = False
        for plot_id in self.plot_ids:
            self.element_states[slot_id][plot_id] = False
        return slot.identifier

    def apply_filter_ray(self, rtdc_ds, slot_id):
        """Convenience function for applying filters to other data

        The filters that are currently set for a specific slot with
        `slot_id` are applied to a dataset.

        Parameters
        ----------
        rtdc_ds: dclab.rtdc_dataset.RTDCBase
            Dataset
        slot_id: str
            Identifier of the slot from which the filters are taken
        """
        # make sure the current ray is built correctly
        self.get_dataset(self.slot_ids.index(slot_id), apply_filter=False)
        # get the ray
        ray = self.get_ray(slot_id)
        ds = ray.get_final_child(rtdc_ds)
        return ds

    def check_contour_spacing(self, plot_id):
        """Check the contour spacing for a specific plot against the data

        This method was implemented to avoid tiny contour spacings for
        plotting, which could lead to OOM events.
        """
        plot = self.plots[self.plot_ids.index(plot_id)]
        plot_state = plot.__getstate__()
        old_plot_state = copy.deepcopy(plot_state)
        if plot_state["general"]["auto range"]:
            for ax in ["x", "y"]:
                feat = plot_state["general"][f"axis {ax}"]
                spacing = plot_state["contour"][f"spacing {ax}"]
                for ds, slot_state in zip(*self.get_plot_datasets(
                        plot_id, apply_filter=False)):
                    slot_id = slot_state["identifier"]
                    slot = self.get_slot(slot_id)
                    sp_min, sp_max = slot.get_sane_spacing_range(feat=feat)
                    if spacing < sp_min:
                        warnings.warn(f"Setting contour spacing for {slot_id} "
                                      f"to minimum ({spacing}<{sp_min})")
                        spacing = sp_min
                    elif spacing > sp_max:
                        warnings.warn(f"Setting contour spacing for {slot_id} "
                                      f"to maximum ({spacing}>{sp_max})")
                        spacing = sp_max
                    plot_state["contour"][f"spacing {ax}"] = spacing
        if old_plot_state != plot_state:
            plot.__setstate__(plot_state)

    def get_dataset(self, slot_index, filt_index=-1, apply_filter=True):
        """Return dataset with all filters updated (optionally applied)

        Parameters
        ----------
        slot_index: int
            index of measurement
        filt_index: int or None
            index of filter; if None, then the plain dataset is returned.
            If negative (default), then the last dataset in the pipeline
            is returned (all selected filters applied).
        apply_filter: bool
            whether to call `dataset.apply_filter` in the end;
            if set to `False`, only the filtering configuration
            of the dataset and its hierarchy parents are updated
        """
        if not isinstance(slot_index, int):
            raise ValueError(
                f"`slot_index` must be an integer, got '{slot_index}'")
        slot = self.slots[slot_index]
        if filt_index is None or (filt_index == -1 and len(self.slots) == 0):
            # return the unfiltered dataset
            ds = slot.get_dataset()
        else:
            slot_id = slot.identifier
            # the filters used
            filters = self.get_filters_for_slot(slot_id=slot_id,
                                                max_filter_index=filt_index)
            # filter ray magic
            ray = self.get_ray(slot.identifier)
            ds = ray.get_dataset(filters, apply_filter=apply_filter)
        return ds

    def get_datasets(self, filt_index=-1, apply_filter=True):
        """Return all datasets with filters applied

        The parameters are passed to :func:`Pipeline.get_dataset`.

        Parameters
        ----------
        filt_index: int or None
            index of filter; if None, then the plain dataset is returned.
            If negative (default), then the last dataset in the pipeline
            is returned (all selected filters applied).
        apply_filter: bool
            whether to call `dataset.apply_filter` in the end;
            if set to `False`, only the filtering configuration
            of the dataset and its hierarchy parents are updated
        """
        kw = {"filt_index": filt_index,
              "apply_filter": apply_filter}
        return [self.get_dataset(ii, **kw) for ii in range(len(self.slots))]

    def get_features(self, scalar=False, label_sort=False, union=False,
                     plot_id=None, ret_labels=False):
        """Return a list of features in the pipeline

        Parameters
        ----------
        scalar: bool
            If True, only return scalar features
        label_sort: bool
            If True, return the features sorted by label
            instead of by feature name
        union: bool
            If True, return the union of features available in all
            slots. If False (default), return only those features
            that are shared by all slots.
        plot_id: None or str
            If set, only datasets that are part of the matching Plot
            instance are used. If None, all datasets of the pipeline
            are used.
        ret_labels: bool
            If True, return the labels as well

        Notes
        -----
        This function returns an empty list if there are no features
        available.
        """
        if union:
            features = set()
        else:
            features = None
        for slot_index in range(self.num_slots):
            slot_id = self.slot_ids[slot_index]
            if (plot_id is None
                or (self.element_states[slot_id][plot_id]
                    and slot_id in self.slots_used)):
                ds = self.get_dataset(slot_index=slot_index, filt_index=None)
                if scalar:
                    ds_features = set(ds.features_scalar)
                else:
                    ds_features = set(ds.features)
                if union:
                    features |= ds_features
                else:
                    if features is None:
                        features = ds_features
                    else:
                        features &= ds_features
        if features is None:
            # This means that the pipeline is empty
            features = []
        labs = [dclab.dfn.get_feature_label(f) for f in features]
        if label_sort:
            lf = sorted(zip(labs, features))
            features = [it[1] for it in lf]
            labs = [it[0] for it in lf]
        else:
            fl = sorted(zip(features, labs))
            features = [it[0] for it in fl]
            labs = [it[1] for it in fl]
        if ret_labels:
            return features, labs
        else:
            return features

    def get_filter(self, filt_id):
        """Return the Filter matching the identifier"""
        if filt_id not in self.filter_ids:
            raise ValueError(f"Filter '{filt_id}' not part of this pipeline!")
        return self.filters[self.filter_ids.index(filt_id)]

    def get_filters_for_slot(self, slot_id, max_filter_index=-1):
        """Return list of filters for a slot

        Parameters
        ----------
        slot_id: str
            identifier of the slot
        max_filter_index: int
            maximum filter index to include in the list. Note that
            some filters may not be applied to a slot, so the final
            length of the returned list may be smaller than this
            value. Set to a negative value (default) to include all
            filters applied to a dataset.
        """
        filters = []
        if max_filter_index < 0:
            # include all filters that are used for this slot
            max_filter_index = len(self.filters) - 1
        for filt_id in self.filter_ids[:max_filter_index + 1]:
            if (self.is_element_active(slot_id, filt_id)
                    and filt_id in self.filters_used):
                filters.append(self.get_filter(filt_id))
        return filters

    def get_min_max(self, feat, plot_id=None, margin=0.0):
        """Return minimum and maximum values for a feature

        Parameters
        ----------
        feat: str
            Feature name
        plot_id: str
            Plot identifier
        margin: float
            Fraction by which the minimum and maximum are
            extended. E.g. for plotting with a 5% margin
            use `margin=0.05`.

        Returns
        -------
        [fmin, fmax]: list of float
            Minimum and maximum values of the feature. If the feature
            is empty or only-nan, an :class:`EmptyDatasetWarning` is
            issued and both return values are set to zero.
        """
        if plot_id is not None:
            dslist = self.get_plot_datasets(plot_id)[0]
        else:
            dslist = self.get_datasets(filt_index=None, apply_filter=False)
        fmin = np.inf
        fmax = -np.inf
        for ds in dslist:
            if np.any(ds.filter.all):
                if feat in ds:
                    fdata = ds[feat][ds.filter.all]
                    invalid = np.isinf(fdata)
                    if np.any(invalid):
                        vdata = fdata[~invalid]
                    else:
                        vdata = fdata
                    if feat in SLOPING_FEATURES:
                        # We are a little faster here.
                        vmin = min(np.nanmin(vdata[:1000]),
                                   np.nanmin(vdata[-1000:]))
                        vmax = max(np.nanmax(vdata[:1000]),
                                   np.nanmax(vdata[-1000:]))
                    else:
                        vmin = np.nanmin(vdata)
                        vmax = np.nanmax(vdata)
                    fmin = min(fmin, vmin)
                    fmax = max(fmax, vmax)
                else:
                    warnings.warn(f"Dataset {ds.identifier} does not "
                                  f"contain the feature '{feat}'!",
                                  MissingFeatureWarning)
            else:
                warnings.warn(f"Dataset {ds.identifier} does not "
                              f"contain any events when filtered!",
                              EmptyDatasetWarning)
        if margin:
            diff = fmax - fmin
            fmin -= margin*diff
            fmax += margin*diff

        if np.any(np.isinf([fmin, fmax])):
            # Set values to 0 if no
            fmin = fmax = 0
        return [fmin, fmax]

    def get_plot(self, plot_id):
        if plot_id not in self.plot_ids:
            raise ValueError(f"Plot '{plot_id}' not part of this pipeline!")
        self.check_contour_spacing(plot_id)
        return self.plots[self.plot_ids.index(plot_id)]

    def get_plot_datasets(self, plot_id, apply_filter=True):
        """Return a list of datasets with slot states that belong to a plot"""
        datasets = []
        states = []
        # keep the same order as in self.slots
        for slot_index in range(len(self.slots)):
            slot = self.slots[slot_index]
            slot_id = slot.identifier
            if (self.element_states[slot_id][plot_id]
                    and slot_id in self.slots_used):
                ds = self.get_dataset(slot_index=slot_index,
                                      apply_filter=apply_filter)
                datasets.append(ds)
                states.append(slot.__getstate__())
        return datasets, states

    def get_plot_col_row_count(self, plot_id, pipeline_state=None):
        """Compute how many rows a plot layout requires

        Parameters
        ----------
        plot_id: str
            identifier of a plot in this pipeline
        pipeline_state: dict
            pipeline state to use; defaults to the current pipeline
            state
        """
        if pipeline_state is None:
            pipeline_state = self.__getstate__()

        # plot state
        for pstate in pipeline_state["plots"]:
            if plot_id == pstate["identifier"]:
                break
        else:
            raise KeyError(f"Plot '{plot_id}' not given in pipeline state!")

        # number of datasets in that plot
        num_scat = 0
        for slot_id in pipeline_state["elements"]:
            num_scat += pipeline_state["elements"][slot_id][plot_id]

        # additional plots
        div = pstate["layout"]["division"]
        if div == "each":
            num_plots = max(1, num_scat)
        elif div == "merge":
            num_plots = 1
        elif div == "multiscatter+contour":
            num_plots = num_scat + 1
        else:
            raise ValueError(f"Unrecognized division: '{div}'")

        # column count
        col_count = min(pstate["layout"]["column count"], num_plots)

        # row count
        row_count = int(np.ceil(num_plots/col_count))
        return col_count, row_count

    def get_ray(self, slot_id):
        """Convenience function that creates and returns a filter ray"""
        # cleanup (just in case)
        for key in list(self.rays.keys()):
            if key not in self.slot_ids:
                self.rays.pop(key)
        if slot_id not in self.rays:
            # create filter ray if it does not exist
            self.rays[slot_id] = FilterRay(self.get_slot(slot_id))
        return self.rays[slot_id]

    def get_slot(self, slot_id):
        """Return the Dataslot matching the RTDCBase identifier"""
        slot_id = slot_id.split("-")[0]  # this is how FilterRay names children
        if slot_id in self.slot_ids:
            slot = self.slots[self.slot_ids.index(slot_id)]
        else:
            raise ValueError(f"Unknown dataset identifier: `{slot_id}`")
        return slot

    def is_element_active(self, slot_id, filt_plot_id):
        return self.element_states[slot_id][filt_plot_id]

    def remove_filter(self, filt_id):
        """Remove a filter by filter identifier"""
        index = self.filter_ids.index(filt_id)
        self.filters.pop(index)
        for slot_id in self.element_states:
            if filt_id in self.element_states[slot_id]:
                self.element_states[slot_id].pop(filt_id)

    def remove_plot(self, plot_id):
        """Remove a filter by plot identifier"""
        index = self.plot_ids.index(plot_id)
        self.plots.pop(index)
        for slot_id in self.element_states:
            if plot_id in self.element_states[slot_id]:
                self.element_states[slot_id].pop(plot_id)

    def remove_slot(self, slot_id):
        """Remove a slot by slot identifier"""
        index = self.slot_ids.index(slot_id)
        self.slots.pop(index)
        if slot_id in self.element_states:
            self.element_states.pop(slot_id)

    def reorder_slots(self, indices):
        """Change the order of data slots

        Parameters
        ----------
        indices: list of ints
            New sequence of slots, i.e. the new slots
            will be `self.slots[indices]`.
        """
        # sanity checks
        if sorted(indices) != list(range(len(self.slots))):
            raise ValueError(f"Cannot reorder slots with inconclusive "
                             f"ordering sequence '{indices}'!")
        new_slots = []
        for idx in indices:
            new_slots.append(self.slots[idx])
        self.slots = new_slots

    def reset(self):
        """Reset the pipeline"""
        self.filters.clear()
        self.plots.clear()
        self.rays.clear()
        self.slots.clear()
        self.element_states.clear()

    def set_element_active(self, slot_id, filt_plot_id, active=True):
        """Activate an element in the block matrix"""
        self.element_states[slot_id][filt_plot_id] = active
