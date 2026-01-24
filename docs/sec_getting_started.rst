===============
Getting started
===============

.. _sec_installation:

Installation
============
DCscope can be installed via multiple channels.

1. **Windows installer:** Download the latest version for your architecture
   (i.e. ``DCscope_X.Y.Z_win_64bit_setup.exe``) from the official
   `release page <https://github.com/DC-analysis/DCscope/releases/latest>`__. 

2. **Python 3.8 with pip:** DCscope can easily be installed with
   `pip <https://pip.pypa.io/en/stable/quickstart/>`__:

   .. code:: bash

       python3 -m pip install dcscope

   To start DCscope, simply run ``python3 -m dcscope``
   or ``dcscope`` in a command shell. 


.. note::

    There used to be macOS builds, but many users reported they were not
    working. Since the GitHub Actions build pipeline works (executable
    binary runs), this is either a CPU architecture issue or some kind of
    macOS safeguard (software signing?). At the moment, we don't have the
    resources to look into this, but we would greatly appreciate help in the
    form of a pull request.


Update
======
DCscope automatically searches for updates (you may opt-out via the
Help menu) and notifies the user when a new version is available.

1. **Windows installer:** The older version of DCscope will be
   automatically uninstalled when installing a new version.

2. **macOS:** The older version of DCscope will be
   automatically uninstalled when installing a new version.

3. **Python 3.8 and pip:**

   .. code:: bash

       pip install --upgrade dcscope


Supported data file formats
===========================
DCscope exclusively supports the .rtdc data file format. This file format is
based on the `HDF5 format <https://en.wikipedia.org/wiki/Hierarchical_Data_Format>`_
which makes it portable, consistent, and efficient.

If you have **.tdms-based datasets** (created using antique versions of Shape-In),
you can still use the data after you have converted them to .rtdc files using
`DCKit <https://github.com/DC-analysis/DCKit/releases/latest>`_,
which provides a convenient GUI for several other RT-DC data
management tasks as well. The .rtdc file format is faster than the .tdms file
format, occupies less disk space, and consists of only one file per measurement.

If you have **raw .rtdc files** that only contain the recorded images and no
extracted events, you can perform segmentation and feature extraction using
`ChipStream <https://github.com/DC-analysis/ChipStream/releases/latest>`_.


How to cite
===========
If you use DCscope in a scientific publication, please cite it with:

.. pull-quote::

   Paul Müller and others (2019), DCscope (formerly Shape-Out) version 2.X.X:
   Graphical user interface for analysis and visualization of RT-DC data sets [Software].
   Available at https://github.com/DC-analysis/DCscope.

If the journal does not accept ``and others``, you can fill in the missing
names in the authors section of the `pyproject.toml file <https://github.com/DC-analysis/DCscope/blob/main/pyproject.toml>`_.
