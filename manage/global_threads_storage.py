import time
import threading
from typing import Callable, Optional, TYPE_CHECKING


if TYPE_CHECKING:
    from flask import Flask


class GlobalThreadsStorage:
    WATCH_INTERVAL_SECONDS = 60

    app: "Flask"
    storage: list["threading.Thread"]
    _storage_lock: "threading.Lock"
    _watcher_thread: Optional["threading.Thread"]

    def __init__(self, app: "Flask"):
        self.app = app
        self.storage = []
        self._storage_lock = threading.Lock()
        self._watcher_thread = None

    def run_in_thread(self, func: Callable, *args, **kwargs) -> "threading.Thread":
        if self._watcher_thread is None:
            raise IOError('Watcher thread not initialized')

        thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        thread.start()

        with self._storage_lock:
            self.storage.append(thread)
            return thread

    def start_watcher(self) -> None:
        self._watcher_thread = threading.Thread(target=self._watcher, name=str(time.time()), daemon=True)
        self._watcher_thread.start()

    def _watcher(self):
        while True:

            # clear finished threads
            with self._storage_lock:
                self.storage = [thread for thread in self.storage if thread.is_alive()]

            time.sleep(self.WATCH_INTERVAL_SECONDS)