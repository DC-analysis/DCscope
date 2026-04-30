import logging
import threading
import time
import traceback

import dclab
from dclab.rtdc_dataset import RTDCBase
import numpy as np
from PyQt6 import QtCore


class EventGetterThread(QtCore.QThread):
    new_event_data = QtCore.pyqtSignal(dict)
    busy_fetching_data = QtCore.pyqtSignal(bool)

    def __init__(self, parent):
        super(EventGetterThread, self).__init__(parent)
        self.worker_lock = threading.Lock()
        self.event_abort = threading.Event()
        self.request = (None, None)
        self.prev_request = (None, None)
        self.logger = logging.getLogger(__name__)
        self.setObjectName(self.__class__.__name__)

    def close(self):
        self.event_abort.set()
        while self.isRunning():
            time.sleep(0.1)

    @QtCore.pyqtSlot(RTDCBase, int)
    def request_event_data(self, ds: RTDCBase, event_index: int):
        with self.worker_lock:
            self.request = (ds, event_index)

    def run(self):
        while not self.event_abort.is_set():
            with self.worker_lock:
                ds, event_index = self.request

            if self.prev_request == (ds, event_index):
                time.sleep(0.05)
                continue

            self.prev_request = (ds, event_index)

            if ds is not None and event_index is not None:
                try:
                    self.busy_fetching_data.emit(True)
                    event_data = self.get_event_data(ds, event_index)
                    self.new_event_data.emit(event_data)
                    if self.prev_request == self.request:
                        self.busy_fetching_data.emit(False)
                except BaseException:
                    self.logger.error(traceback.format_exc())
            else:
                time.sleep(0.01)

    def get_event_data(self, ds: RTDCBase, event_index: int):
        """Return all event data relevant for QuickView visualization"""
        data = {}
        data["index"] = event_index
        try:
            # Image data
            for feat in ["image", "image_bg", "mask", "qpi_amp", "qpi_pha"]:
                if feat in ds:
                    data[feat] = ds[feat][event_index]

            # Trace data
            if "trace" in ds:
                try:
                    data["traces"] = self.get_event_traces(ds, event_index)
                except BaseException:
                    self.logger.error(traceback.format_exc())
        except IndexError:
            if event_index != 0:
                data = self.get_event_data(ds, 0)
            else:
                self.logger.error(traceback.format_exc())
        return data

    def get_event_traces(self,
                         ds: RTDCBase,
                         event_index: int,
                         ):
        """Return all trace data"""
        tdata = {}
        # time axis
        flsamples = ds.config["fluorescence"]["samples per event"]
        flrate = ds.config["fluorescence"]["sample rate"]
        fltime = np.arange(flsamples) / flrate * 1e6
        tdata["time"] = fltime

        # fluorescence traces and pos/width/max features
        range_fl = [0, 0]
        for name in dclab.dfn.FLUOR_TRACES:
            flid = name.split("_")[0]
            if name in ds["trace"]:
                # show the trace information
                tracey = ds["trace"][name][event_index]  # trace data
                range_fl[0] = min(range_fl[0], tracey.min())
                range_fl[1] = max(range_fl[1], tracey.max())
                tdata[name] = tracey
                for which in ["pos", "width", "max"]:
                    feat = f"{flid}_{which}"
                    if feat not in tdata:
                        tdata[feat] = ds[feat][event_index]

        return tdata
