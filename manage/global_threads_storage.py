import time
import threading
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from typing import Callable, Optional, TYPE_CHECKING


if TYPE_CHECKING:
    from flask import Flask
    from concurrent.futures import Future


class GlobalThreadsStorage:
    WATCH_INTERVAL_SECONDS = 60

    app: "Flask"
    storage: Queue["Future"]
    executor: ThreadPoolExecutor

    def __init__(self, app: "Flask"):
        self.app = app
        self.storage = Queue()
        self.executor = ThreadPoolExecutor(max_workers=5)

    def wrap_in_context(self, func: Callable, *args, **kwargs):
        """ Wrap in Flask app content """
        with self.app.app_context():
            with self.app.test_request_context():
                return func(*args, **kwargs)

    def run_in_thread(self, func: Callable, *args, **kwargs) -> "Future":
        """ Send to queue of background executing """
        return self.executor.submit(func, *args, **kwargs)
