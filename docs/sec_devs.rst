=================
Developer's Guide
=================

If you are here, then you would like to contribute to Shape-Out.
Some parts of this document might need improvement and corrections.


Versioning
==========
We try to adhere to `semantic versioning <https://semver.org/>`_
Shape-Out uses `setuptools-scm <https://setuptools-scm.readthedocs.io>`_
to automatically determine the version from the latest Git tag.

Setuptools-scm might cause problems for you if you are working on your own fork
or branch and after installing Shape-Out in your local environment you get
a version like `0.0.0post1421_cdqut`. The solution is to pull the
tags from the main repository and after that install Shape-Out again.

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
The `documentation <https://shapeout2.readthedocs.io>`_ is automatically built
and deployed by readthedocs.io.

Pull Requests
=============
The ideal route of contribution is via pull requests into the `main` branch.
Make sure to

- name your forked branch after problem you are addressing
- update the changelog correctly
- all tests and linting (`flake8`) pass in CI


GUI development
===============
Shape-Out is based on the `Qt6 <https://doc.qt.io/qt-6>`_ framework.
This means you can use `QtCreator/QtDesigner <https://www.youtube.com/watch?v=ot94H3-d5d8>`_
to graphically design the `.ui` files that are then loaded when starting Shape-Out.
We use `PyQt6` (not `PySide6`) to interface with Qt.

Note that for some reason, new versions of QtDesigner produce .ui files
that are incompatible with `pyuic6` (which converts the .ui files into
Python code). As a result, we have to use QtCreator 8 in order for things
to work (If you have a better solution, please let us know.):
https://github.com/qt-creator/qt-creator/releases/tag/v8.0.2

The .ui files are loaded directly into Shape-Out and are not (as it is
shown in many tutorials) converted to .py files and added to git versioning.
If this annoys you, because it makes your development experience (e.g. code
completion) unbearable: Feel free to scratch that itch and migrate Shape-Out
to the .py-style scheme. The only requirements for that to be merged are:

- put all .ui files in a directory called `ui` in the root of the repository
- make sure the .ui files are included in the .tar.gz Python source distributable
- write a script that automatically converts all .ui files to .py files in
  the correct locations
- exclude the automatically generated .py files from linting
- add a GitHub Action that makes sure that changes in the .ui files
  are reflected in the .py files (to prevent a developer from forgetting
  to build the .py files)
