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
        self.setObjectName(self.__class__.__name__ + "_" + target.__name__)

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


def run_async_class(func):
    """Decorator for running a function in the background in a class

    The class must implement

        self._async_runners = []
        self._event_close = Threading.Event()

    and the following method:

        def closeEvent(self, event):
            self._event_close.set()
            for runner in self._async_runners:
                if runner.isRunning():
                    runner.wait()

    The called method should check `self._event_close.is_set()` and
    abort when the event is set.
    """
    @wraps(func)
    def async_func(inst, *args, **kwargs):
        runner = Runner(func, inst, *args, **kwargs)
        # Keep the runner somewhere or it will be destroyed
        inst._async_runners.append(runner)
        runner.start()

    return async_func
