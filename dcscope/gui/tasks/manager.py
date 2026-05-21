import logging
import threading
import uuid

from PyQt6 import QtCore

from .worker import TaskWorker


class TaskManager(QtCore.QObject):
    quit_threads = QtCore.pyqtSignal()
    task_done = QtCore.pyqtSignal(dict, object)  # (task, result)
    task_error = QtCore.pyqtSignal(dict, object)  # (task, error)

    def __init__(self, parent):
        super(TaskManager, self).__init__(parent=parent)
        self.logger = logging.getLogger(__name__)

        self.task_queues = {}

        # threads in which the workers run
        self.threads = [QtCore.QThread()]
        for ii, thread in enumerate(self.threads):
            self.quit_threads.connect(thread.quit)
            thread.setObjectName(f"TaskThread-{ii}")
            thread.start()
            self.logger.info(f"Started {thread}")

        # workers
        self.workers = []
        for thread in self.threads:
            worker = TaskWorker()
            worker.moveToThread(thread)
            worker.task_done.connect(self.task_done)
            worker.task_error.connect(self.task_error)
            self.workers.append(worker)

        # to make sure running next task is only run once at a time
        self.lock_run_next = threading.Lock()

        # checks incoming queue for new tasks
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._run_next_task_in_thread)
        self.timer.start(500)

    @property
    def num_tasks_running(self):
        """Number of tasks currently running"""
        num = 0
        for worker in self.workers:
            num += worker.current_task_id is not None
        return num

    @property
    def num_tasks_queued(self):
        """Number of tasks currently queued"""
        num = 0
        for q in self.task_queues.values():
            num += len(q)
        return num

    def abort_task(self,
                   task: dict,
                   raise_if_not_found: bool = True,
                   ) -> None:
        """Abort the specified task

        Raises KeyError if a task cannot be found and `raise_if_not_found`
        is True. This might be the case if a lot of tasks ran after the task.
        """
        with self.lock_run_next:
            # check the queues
            for q in self.task_queues.values():
                for ii, item in enumerate(q):
                    if item["identifier"] == task["identifier"]:
                        q.pop(ii)
                        return

            # check the workers
            for worker in self.workers:
                try:
                    worker.abort_task(task)
                except KeyError:
                    continue
                else:
                    return

        # task was not found
        if raise_if_not_found:
            raise KeyError(f"Could not find task {task['identifier']}")

    def add_task(self,
                 task: dict,
                 topic: str = "general",
                 communicate_progress: QtCore.PYQT_SIGNAL | None = None,
                 communicate_message: QtCore.PYQT_SIGNAL | None = None,
                 reset_topic: bool = False):
        """Add a new task to the queue

        Tasks are fetched and executed in threads when `self.timer` times out.

        The task dictionary must contain three entries:

        - "func": callable function which accepts the argument
                  "progress", a callable expecting (float, str) as argument
                  (progress goes from 0 to 1, string is progress message)
        - "args": arguments to the function
        - "kwargs": keyword arguments to the function
        """
        if "identifier" not in task:
            task["identifier"] = str(uuid.uuid4())

        if topic not in self.task_queues:
            self.task_queues[topic] = []
        q = self.task_queues[topic]

        # We don't want any of the previous tasks being processed.
        if reset_topic:
            q.clear()

        q.append((task, communicate_progress, communicate_message))
        self.logger.info(f"Queued task '{task['identifier']}'")

    def close(self):
        self.quit_threads.emit()
        for thread in self.threads:
            self.logger.info(f"Waiting for {thread}")
            thread.wait()

    def get_task_result(self, task):
        task_id = task["identifier"]
        for worker in self.workers:
            if task_id in worker.results:
                return worker.results.pop(task_id)
        else:
            raise KeyError(f"Could not find result for task '{task_id}'.")

    def is_task_finished(self, task) -> bool:
        """Check whether the task is finished"""
        for worker in self.workers:
            if task["identifier"] in worker.tasks_done:
                return True
        else:
            return False

    def is_task_running(self, task) -> bool:
        """Check whether the task is finished"""
        for worker in self.workers:
            if worker.current_task_id == task["identifier"]:
                return True
        else:
            return False

    def _run_next_task_in_thread(self):
        """Run the next task in a thread"""
        if self.lock_run_next.locked():
            return

        with self.lock_run_next:
            for _ in range(len(self.threads)):
                for q in self.task_queues.values():
                    if len(q):
                        task_tuple = q.pop(0)
                        break
                else:
                    # nothing to do
                    return

                for worker in self.workers:
                    if worker.event_busy.is_set():
                        continue
                    else:
                        task, comm_progress, comm_message = task_tuple

                        worker.disconnect_progress_handles()
                        worker.connect_progress_handles(
                            comm_progress, comm_message)

                        worker.do_task.emit(task)
                        self.logger.info(
                            f"Running task '{task['identifier']}' "
                            f"in '{worker.thread()}'")
                        break
                else:
                    # put the task back in the queue
                    q.insert(0, task_tuple)
                    # all workers are busy, so we do not need to keep trying
                    break
