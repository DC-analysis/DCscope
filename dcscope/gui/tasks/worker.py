from __future__ import annotations
import inspect
import threading
import traceback

from PyQt6 import QtCore


class TaskAbortError(BaseException):
    """Used for aborting a task"""
    pass


class TaskWorker(QtCore.QObject):
    task_done = QtCore.pyqtSignal(dict, object)
    task_error = QtCore.pyqtSignal(dict, object)
    communicate_progress = QtCore.pyqtSignal(object)  # int or float possible
    communicate_message = QtCore.pyqtSignal(str)
    do_task = QtCore.pyqtSignal(dict)

    def __init__(self, *args, **kwargs):
        """Task worker for progressing tasks in background

        The worker is meant to be put in another thread using `moveToThread()`.
        """
        super(TaskWorker, self).__init__(*args, **kwargs)
        self.event_busy = threading.Event()
        self.event_abort = threading.Event()
        self.state_lock = threading.Lock()
        self._progress_handles = None
        self.current_task_id = None
        self.do_task.connect(self.run_task)

    @QtCore.pyqtSlot()
    def _dummy_progress(self):
        return None

    def connect_progress_handles(self,
                                 communicate_progress,
                                 communicate_message):
        # If the communication methods are not given, then use a dummy method.
        # If the task "func" supports progress monitoring, then we will be
        # able to abort it with `TaskAbortError`.
        if communicate_progress is None:
            communicate_progress = self._dummy_progress
        if communicate_message is None:
            communicate_message = self._dummy_progress

        self.communicate_message.connect(communicate_message)
        self.communicate_progress.connect(communicate_progress)
        self._progress_handles = (
            communicate_progress, communicate_message)

    def disconnect_progress_handles(self):
        if self._progress_handles is not None:
            communicate_progress, communicate_message = self._progress_handles
            if communicate_progress is not None:
                self.communicate_progress.disconnect(communicate_progress)
            if communicate_message is not None:
                self.communicate_message.disconnect(communicate_message)
            self._progress_handles = None

    def abort_task(self, task: dict):
        """Abort a task by setting `self.event_abort`

        This will raise `TaskAbortError` whenever the underlying method
        calls their "communicate_message" or "communicate_progress"
        method, forcing it to exit at these predefined break points.
        """
        task_id = task["identifier"]
        with self.state_lock:
            if self.current_task_id == task_id:
                self.event_abort.set()
                task["status"] = "aborted"
            elif task.get("status") == "done":
                pass
            else:
                raise KeyError(f"{self} does not run task '{task_id}'")

    def communicate_message_wrapper(self, *args):
        """Wrapper for "communicate_message" function

        Checks `self.event_abort` and raises `TaskAbortError`.
        """
        if self.event_abort.is_set():
            raise TaskAbortError(f"Task '{self.current_task_id}' aborted")
        self.communicate_message.emit(*args)

    def communicate_progress_wrapper(self, *args):
        """Wrapper for "communicate_progress" function

        Checks `self.event_abort` and raises `TaskAbortError`.
        """
        if self.event_abort.is_set():
            raise TaskAbortError(f"Task '{self.current_task_id}' aborted")
        self.communicate_progress.emit(*args)

    @QtCore.pyqtSlot(object)
    def run_task(self, task: dict):
        with self.state_lock:
            self.event_busy.set()
            self.event_abort.clear()
        self.current_task_id = task["identifier"]
        try:
            func = task["func"]
            args = task.get("args", [])
            kwargs = task.get("kwargs", {})
            spec = inspect.getfullargspec(func)
            kw_list = spec.args + spec.kwonlyargs

            # tracking and aborting is optional
            if "communicate_message" in kw_list:
                kwargs["communicate_message"] = \
                    self.communicate_message_wrapper
            if "communicate_progress" in kw_list:
                kwargs["communicate_progress"] = \
                    self.communicate_progress_wrapper
            if "event_abort" in kw_list:
                kwargs["event_abort"] = self.event_abort
            result = func(*args, **kwargs)
        except TaskAbortError:
            # task intentionally aborted
            pass
        except BaseException as e:
            print(traceback.format_exc())
            self.task_error.emit(task, e)
            task["status"] = "error"
            task["error"] = e
        else:
            if not self.event_abort.is_set():
                task["status"] = "done"
                task["result"] = result
                self.task_done.emit(task, result)

        self.current_task_id = None
        with self.state_lock:
            self.event_busy.clear()
            self.event_abort.clear()
