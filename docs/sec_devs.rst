=================
Developer's Guide
=================

If you are here, then you would like to contribute to DCscope.
Some parts of this document might need improvement and corrections.


Versioning
==========
We try to adhere to `semantic versioning <https://semver.org/>`_.
DCscope uses `setuptools-scm <https://setuptools-scm.readthedocs.io>`_
to automatically determine the version from the latest Git tag.

Setuptools-scm might cause problems for you if you are working on your own fork
or branch and after installing DCscope in your local environment you get
a version like `0.0.0post1421_cdqut`. The solution is to pull the
tags from the main repository and after that install DCscope again.

If you have figured out how to do this, please update this document with
a PR :).


Changelog
=========
The `CHANGELOG` in the root of the repository consists of the corresponding
git tags and the changes that were made in-between.
We try to adhere to `conventional commits <https://www.conventionalcommits.org>`_.

Ideally, each entry in the changelog corresponds to one Git commit,
but of course, this is not always feasible. You might want to read through
the document to get an idea.

Note that there is only one changelog which might cause merge conflicts
when you are making a PR. We might want to switch to something else in the
future, but for now we keep this single-file system for the sake of simplicity.

Also note that if you are adding a new feature/enhancement/bugfix, make
sure to properly increment the (possibly existing) future tag in the changelog.
E.g. if the current version is "2.1.0" and somebody else made a bugfix, adding
"2.1.1" to the changelog, then if you implement a new feature, you have to
replace "2.1.1" with "2.2.0" in the changelog (because a new feature bumps
the minor version).


CI/CD
=====
We use GitHub Actions for testing and building artifacts for releases.
Check the `.github/workflows` directory.


Documentation
=============
The documentation is built using `sphinx <https://www.sphinx-doc.org/>`_.
To build the documentation, simply run this in the root of the repository::

    # install the project, if not already done
    pip install -e .
    # install requirements for docs, if not already done
    pip install -r docs/requirements.txt
    # go to the docs directory
    cd docs
    # build the docs
    sphinx-build . _build

You can then open `_build/index.html` in your browser.
The `documentation <https://dcscope.readthedocs.io>`_ is automatically built
and deployed by readthedocs.io.

Pull Requests
=============
The ideal route of contribution is via pull requests into the `main` branch.
Make sure to

- name your forked branch after the problem you are addressing
- update the changelog correctly
- have all tests and linting (`flake8`) pass in CI


GUI development
===============
DCscope is based on the `Qt6 <https://doc.qt.io/qt-6>`_ framework.
This means you can use `QtCreator/QtDesigner <https://www.youtube.com/watch?v=ot94H3-d5d8>`_
to graphically design the user interface. The `.ui` files are located in the
`ui` directory in the root of the repository.
We use `PyQt6` (not `PySide6`) to interface with Qt.

The .ui files are converted to Python files (`*_ui.py`) in the
corresponding locations in the `dcscope/gui` directory with the
`ui/run_uic.sh` script (which calls `pyuic6`). The generated `*_ui.py`
files are committed to the repository and excluded from linting.
Whenever you modify a .ui file, run `ui/run_uic.sh` and commit the
resulting changes in the `*_ui.py` files as well. Never edit the
`*_ui.py` files by hand, because your changes will be overwritten the
next time the script is run.
