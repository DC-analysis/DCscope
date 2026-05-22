import time

from PyQt6 import QtWidgets, QtTest

from dcscope.gui.tasks import TaskManager

import pytest


def test_task_empty(qtbot):
    mw = QtWidgets.QMainWindow()
    tm = TaskManager(mw)
    assert len(tm.workers) == 1
    assert len(tm.threads) == 1
    tm.close()


def test_task_simple(qtbot):
    mw = QtWidgets.QMainWindow()

    def method(argument):
        return argument * 2

    tm = TaskManager(mw)

    task = {
        "func": method,
        "args": [1],
        "kwargs": {},
    }

    tm.add_task(task)
    assert "identifier" in task

    while not tm.is_task_finished(task):
        QtTest.QTest.qWait(100)

    assert tm.get_task_result(task) == 2
    tm.close()


def test_task_abort(qtbot):
    mw = QtWidgets.QMainWindow()

    def communicator_for_progress(value):
        print(f"Progress: {value}")

    def method(argument, communicate_progress):
        # give manager enough time to abort this job
        for ii in range(100):
            # call this method to trigger the TaskAbortError exceptin in worker
            communicate_progress(0.3 * ii)
            time.sleep(0.1)
        return argument * 2

    tm = TaskManager(mw)

    task = {
        "func": method,
        "args": [1],
        "kwargs": {},
    }

    tm.add_task(
        task,
        communicate_progress=communicator_for_progress
    )
    assert "identifier" in task

    while not tm.is_task_running(task):
        QtTest.QTest.qWait(100)

    tm.abort_task(task)

    while tm.is_task_running(task):
        QtTest.QTest.qWait(100)

    # there should not be any result
    with pytest.raises(KeyError, match="is not completed"):
        tm.get_task_result(task)

    tm.close()


def test_task_error(qtbot):
    mw = QtWidgets.QMainWindow()

    error_data = {}

    def method(argument):
        raise ValueError("A TEST ERROR")

    def on_error(task, error):
        error_data["test"] = task, error

    tm = TaskManager(mw)
    tm.task_error.connect(on_error)

    task = {
        "func": method,
        "args": [1],
        "kwargs": {},
    }

    tm.add_task(task)
    assert "identifier" in task

    while tm.num_tasks_queued + tm.num_tasks_running:
        QtTest.QTest.qWait(100)

    # there should not be any result
    with pytest.raises(KeyError, match="is not completed"):
        tm.get_task_result(task)

    # the error message should be there
    assert error_data["test"][0] == task
    assert error_data["test"][1].__class__ == ValueError
    assert error_data["test"][1].args[0] == "A TEST ERROR"

    error_data_2 = tm.get_task_error(task)
    assert error_data_2.__class__ == ValueError
    assert error_data_2.args[0] == "A TEST ERROR"

    tm.close()


def test_task_tracking(qtbot):
    mw = QtWidgets.QMainWindow()

    data = {"test_progress": 0}

    def communicator_for_progress(value):
        data["test_progress"] = value

    def method(argument, communicate_progress):
        communicate_progress(0.3)
        return argument * 2

    tm = TaskManager(mw)

    task = {
        "func": method,
        "args": [1],
        "kwargs": {},
    }

    tm.add_task(
        task,
        communicate_progress=communicator_for_progress
    )
    assert "identifier" in task

    while not tm.is_task_finished(task):
        QtTest.QTest.qWait(100)

    assert tm.get_task_result(task) == 2
    assert data["test_progress"] == 0.3
    tm.close()
