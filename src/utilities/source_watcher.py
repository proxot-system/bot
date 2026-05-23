import threading
import time
from pathlib import Path
from threading import Thread
from typing import Any, Callable

from watchdog.events import FileModifiedEvent as _fme
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from utilities.config import get_config

FileModifiedEvent = _fme

Predicate = Callable[[FileModifiedEvent], bool]
subscribers: list[tuple[int, Predicate, Callable[[FileModifiedEvent], Any]]] = []


class FileWatcher(FileSystemEventHandler):
	def __init__(self, delay=0.5):
		self.delay = delay
		self.timers = {}
		self.lock = threading.Lock()

	def on_modified(self, event: FileModifiedEvent):
		if not isinstance(event, FileModifiedEvent):
			return

		path = str(event.src_path)
		if path.endswith("4913") and get_config("watcher.ignore-4913", typecheck=bool):
			return

		path = path.replace("\\", "/")

		with self.lock:
			if path in self.timers:
				self.timers[path].cancel()
			t = threading.Timer(self.delay, self._dispatch_debounced, args=[event])
			self.timers[path] = t
			t.start()

	def _dispatch_debounced(self, event):
		path = str(event.src_path).replace("\\", "/")

		with self.lock:
			self.timers.pop(path, None)

		for _, predicate, callback in subscribers:
			if predicate(event):
				callback(event)


id = 0


def subscribe(predicate: Callable[[FileModifiedEvent], bool], cb: Callable[[FileModifiedEvent], Any]):
	global id
	id += 1
	subscribers.append((id, predicate, cb))


def watch():
	observer = Observer()
	observer.schedule(
		FileWatcher(),
		path="src/",
		recursive=True,
		event_filter=[FileModifiedEvent],
	)
	observer.start()

	try:
		while True:
			time.sleep(60 * 60 * 24)
	except KeyboardInterrupt:
		observer.stop()
	observer.join()


def filter_startswith(starts: str) -> Predicate:
	return lambda event: str(event.src_path).startswith(starts)


def filter_file_suffix(suffix: str) -> Predicate:
	return lambda event: Path(str(event.src_path)).suffix == suffix


def filter_endswith(ends: str) -> Predicate:
	return lambda event: str(event.src_path).endswith(ends)


def filter_path(path: str) -> Predicate:
	return lambda event: str(event.src_path).startswith(path)


def all_of(*predicates) -> Predicate:
	return lambda event: all(p(event) for p in predicates)


def any_of(*predicates) -> Predicate:
	return lambda event: any(p(event) for p in predicates)


watcher_thread = Thread(target=watch)
watcher_thread.daemon = True
watcher_thread.start()
