import dclab


class FilterRay(object):
    def __init__(self, slot):
        """Manages filter-based dataset hierarchies

        Filter rays are used to cache RTDCBase filter-hierarchy
        children.
        """
        #: identifier of the ray (matches the slot)
        self.identifier = slot.identifier
        #: slot defining the ray
        self.slot = slot
        #: segments of the filter ray, consisting of hash, previous, and
        #: next dataset
        self.segments = []
        # holds the filters (protected so that users use set_filters)
        self._filters = []
        # used for testing (incremented when the ray is cut)
        self._generation = 0
        # used for checking validity of the ray
        self._slot_hash = "unset"

    def __repr__(self):
        repre = "<Pipeline Filter Ray '{}' at {}>".format(self.identifier,
                                                          hex(id(self)))
        return repre

    def _add_segment(self, ds, filt):
        """Add a filter segment"""
        ds.reset_filter()
        filt.update_dataset(ds)
        child = self._new_child(ds, filt)
        self.segments.append([filt.hash, ds, child])
        return child

    def _new_child(self, ds, filt=None, apply_filter=False):
        identifier = self.slot.identifier
        if filt is None:
            identifier += "-root"
        else:
            identifier += "-" + filt.identifier + "-child"
        ds = dclab.rtdc_dataset.RTDC_Hierarchy(
            ds, apply_filter=apply_filter, identifier=identifier)
        return ds

    @property
    def filters(self):
        """filters currently used by the ray

        Notes
        -----
        This list may not be up-to-date. If you would like to
        get the current list of filters for a dataset, always
        use :func:`.Pipeline.get_filters_for_slot`.
        """
        return self._filters

    def get_final_child(self, rtdc_ds=None, filters=None, apply_filter=True):
        """Return the final ray child of `rtdc_ds`

        If `rtdc_ds` is None, then the dataset of the current
        ray (self.slot) is used. If `rtdc_ds` is given, then
        no ray caching is performed and the present ray is not
        modified.

        This is a convenience function used when the filter ray
        must be applied to a different dataset (not the one in
        `self.slot`). This is used in DCscope when a filter ray
        is applied to other data on disk e.g. when computing
        statistics. For regular use of the filter ray in a
        pipeline, use :func:`get_dataset`.

        .. versionchanged:: 2.25.1
          The dataset returned is a clean child dataset without any
          filters defined.

        """
        if filters is None:
            filters = self.filters
            external_filt = False
        else:
            external_filt = True

        if rtdc_ds is None:
            # normal case
            external_ds = False
            ds = self.slot.get_dataset()
        else:
            # ray is applied to other data
            external_ds = True
            # do not modify the original dataset (create a child to work with)
            ds = self._new_child(rtdc_ds)

        # Dear future self,
        #
        # don't even think about filter ray branching.
        #
        # Sincerely,
        # past self

        filters = [f for f in filters if f.filter_used]

        if filters:
            # apply all filters
            for ii, filt in enumerate(filters):
                # remember the previous hierarchy parent
                # (ds is always used for the next iteration)
                if external_ds or external_filt:
                    # do not touch self.segments
                    filt.update_dataset(ds)
                    ds = self._new_child(ds, filt)
                elif len(self.segments) < ii + 1:
                    # just create a new segment
                    ds = self._add_segment(ds, filt)
                elif filt.hash != self.segments[ii][0]:
                    # the filter ray is changing here;
                    # trim it and add a new segment
                    self.segments = self.segments[:ii]
                    ds = self._add_segment(ds, filt)
                    self._generation += 1  # for testing
                else:
                    # reuse previous segment
                    ds = self.segments[ii][2]
            final_ds = ds
        else:
            final_ds = ds

        if not external_ds:
            ds.reset_filter()

        if apply_filter:
            final_ds.apply_filter()

        return final_ds

    def get_dataset(self, apply_filter=True):
        """Return the dataset that corresponds to applying these filters

        Parameters
        ----------
        apply_filter: bool
            Whether to apply all filters and update the metadata of
            the requested dataset. This should be True if you are
            intending to work with the resulting data. You can set
            it to false if you would just like to fetch the dataset,
            apply some more filters and then call `rejuvenate`
            yourself.
        """
        # compute the final hierarchy child
        ds = self.get_final_child(apply_filter=apply_filter)
        return ds

    def set_filters(self, filters):
        """Set the filters of the current ray"""
        # only take into account active filters
        self._filters = filters
