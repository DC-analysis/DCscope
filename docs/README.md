DCscope documentation
=======================
Building the documentation of DCscope requires Python 3.10 or newer.
To install DCscope and the requirements for building the documentation,
run (in the `docs` directory)

    pip install -e ..
    pip install -r requirements.txt

To compile the documentation, run

    sphinx-build . _build

Notes
=====
To view the sphinx inventory of DCscope, run

   python -m sphinx.ext.intersphinx 'http://dcscope.readthedocs.io/en/latest/objects.inv'
