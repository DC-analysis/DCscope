"""Convenience methods/classes for running things in the background

This module uses QThread for background processes.
There is integration with QProgressbar and QProgressDialog.
"""
from .manager import TaskManager  # noqa: F401
from .worker import TaskAbortError  # noqa: F401
