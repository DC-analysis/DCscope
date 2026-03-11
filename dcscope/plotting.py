from dclab.kde import KernelDensityEstimator


def get_contour_lines(rtdc_ds, xax, yax, xacc, yacc, xscale, yscale,
                      kde_type="histogram", kde_kwargs=None, quantiles=None):
    """Return contour lines using :class:`dclab.kde.KernelDensityEstimator`"""
    rtdc_ds.apply_filter()
    # compute contour plot data
    kde_instance = KernelDensityEstimator(rtdc_ds=rtdc_ds)
    contours = kde_instance.get_contour_lines(
        quantiles=quantiles,
        xax=xax,
        yax=yax,
        xacc=xacc,
        yacc=yacc,
        xscale=xscale,
        yscale=yscale,
        kde_type=kde_type,
        kde_kwargs=kde_kwargs)
    return contours


def get_scatter_data(rtdc_ds, downsample, xax, yax, xscale, yscale,
                     kde_type="histogram", kde_kwargs=None):
    """Return scatter data using :class:`dclab.kde.KernelDensityEstimator`"""
    rtdc_ds.apply_filter()
    # compute scatter plot data
    x, y, idx = rtdc_ds.get_downsampled_scatter(
        xax=xax,
        yax=yax,
        downsample=downsample,
        xscale=xscale,
        yscale=yscale,
        remove_invalid=True,
        ret_mask=True)
    # kde
    kde_instance = KernelDensityEstimator(rtdc_ds=rtdc_ds)
    kde = kde_instance.get_scatter(
        xax=xax, yax=yax, positions=(x, y), kde_type=kde_type,
        kde_kwargs=kde_kwargs, xscale=xscale, yscale=yscale
    )
    if kde.size and kde.min() != kde.max():
        kde -= kde.min()
        kde /= kde.max()
    return x, y, kde, idx
