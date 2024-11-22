|ShapeOut2|
===========

|PyPI Version| |Build Status| |Coverage Status| |Docs Status|


**Shape-Out 2** is the successor of
`Shape-Out <https://github.com/ZELLMECHANIK-DRESDEN/ShapeOut>`__,
a graphical user interface for the analysis and visualization of RT-DC data sets.
For more information please visit https://zellmechanik.com/.


Documentation
-------------

The documentation, including the code reference and examples, is available at
`shapeout2.readthedocs.io <https://shapeout2.readthedocs.io>`__.


Installation
------------
Installers for Windows and macOS are available at the `release page <https://github.com/ZELLMECHANIK-DRESDEN/ShapeOut2/releases>`__.

If you have Python 3 installed, you can install Shape-Out 2 with

::

    pip install shapeout2


Citing Shape-Out
----------------
Please cite Shape-Out either in-line

::

  (...) using the analysis software Shape-Out version 2.X.X (available at
  https://github.com/ZELLMECHANIK-DRESDEN/ShapeOut2).

or in a bibliography

::

  Paul Müller and others (2019), Shape-Out version 2.X.X: Analysis software
  for real-time deformability cytometry [Software]. Available at
  https://github.com/ZELLMECHANIK-DRESDEN/ShapeOut2.

and replace ``2.X.X`` with the version of Shape-Out that you used.


Testing
-------

::

    pip install -e .
    pip install -r tests/requirements.txt
    pytest tests


.. |ShapeOut2| image:: https://raw.github.com/ZELLMECHANIK-DRESDEN/ShapeOut2/master/docs/logo/shapeout2_h50.png
.. |PyPI Version| image:: https://img.shields.io/pypi/v/ShapeOut2.svg
   :target: https://pypi.python.org/pypi/ShapeOut2
.. |Build Status| image:: https://img.shields.io/github/actions/workflow/status/ZELLMECHANIK-DRESDEN/ShapeOut2/check.yml?branch=master
   :target: https://github.com/ZELLMECHANIK-DRESDEN/ShapeOut2/actions?query=workflow%3AChecks
.. |Coverage Status| image:: https://img.shields.io/codecov/c/github/ZELLMECHANIK-DRESDEN/ShapeOut2/master.svg
   :target: https://codecov.io/gh/ZELLMECHANIK-DRESDEN/ShapeOut2
.. |Docs Status| image:: https://img.shields.io/readthedocs/shapeout2
   :target: https://readthedocs.org/projects/shapeout2/builds/
