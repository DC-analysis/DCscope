"""https://stackoverflow.com/questions/39304951/"""
from functools import wraps

from PyQt6 import QtCore


class Runner(QtCore.QThread):
    """Runs a function in the background"""

    def __init__(self, target, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._target = target
        self._args = args
        self._kwargs = kwargs

    def run(self):
        self._target(*self._args, **self._kwargs)


def run_async(func):
    """Decorator for running a function in the background"""
    @wraps(func)
    def async_func(*args, **kwargs):
        runner = Runner(func, *args, **kwargs)
        # Keep the runner somewhere or it will be destroyed
        func.__runner = runner
        runner.start()

    return async_func
