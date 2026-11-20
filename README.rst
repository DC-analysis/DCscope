|DCscope|
===========

|PyPI Version| |Build Status| |Coverage Status| |Docs Status|


**DCscope** (formerly Shape-Out) is a graphical user interface for the
analysis and visualization of RT-DC datasets.


Documentation
-------------

The documentation, including the code reference and examples, is available at
`dcscope.readthedocs.io <https://dcscope.readthedocs.io>`__.


Installation
------------
Installers for Windows are available at the `release page <https://github.com/DC-analysis/DCscope/releases>`__.

If you have Python 3 installed, you can install DCscope with

::

    pip install dcscope


Citing DCscope
----------------
Please cite DCscope either in-line

::

  (...) using the analysis software DCscope (formerly Shape-Out) version 2.X.X
  (available at https://github.com/DC-analysis/DCscope).

or in a bibliography

::

  Paul Müller and others (2019), DCscope (formerly Shape-Out) version 2.X.X:
  Analysis software for real-time deformability cytometry [Software].
  Available at https://github.com/DC-analysis/DCscope.

and replace ``2.X.X`` with the version of DCscope that you used.


Testing
-------

::

    pip install -e .
    pip install -r tests/requirements.txt
    pytest tests


.. |DCscope| image:: https://raw.github.com/DC-analysis/DCscope/main/dcscope/img/splash.png
.. |PyPI Version| image:: https://img.shields.io/pypi/v/DCscope.svg
   :target: https://pypi.python.org/pypi/DCscope
.. |Build Status| image:: https://img.shields.io/github/actions/workflow/status/DC-analysis/DCscope/check.yml?branch=main
   :target: https://github.com/DC-analysis/DCscope/actions?query=workflow%3AChecks
.. |Coverage Status| image:: https://img.shields.io/codecov/c/github/DC-analysis/DCscope/main.svg
   :target: https://codecov.io/gh/DC-analysis/DCscope
.. |Docs Status| image:: https://img.shields.io/readthedocs/dcscope
   :target: https://readthedocs.org/projects/dcscope/builds/
