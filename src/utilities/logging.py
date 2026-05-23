import logging
import os
import time

from utilities.config import debugging, get_config


class IgnoreFilter(logging.Filter):
	def __init__(self, ignored):
		super().__init__()
		self.ignored = ignored

	def filter(self, message):
		return not any(ignored_msg in message.getMessage() for ignored_msg in self.ignored)


logs_path = "./logs"
os.makedirs(logs_path, exist_ok=True)
ignored = [
	"❤ Gateway is sending a Heartbeat",
	"❤ Received heartbeat acknowledgement from gateway",
	'Sending data to websocket: {"op": 1, "d": 18}',
]

loggingLevel = logging.getLevelName(get_config(f"bot{'' if debugging() else '.prod'}.logging-level").upper())


def createLogger(name: str):
	logger = logging.getLogger(name)
	logger.setLevel(loggingLevel)

	formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

	for handler in [
		logging.FileHandler(f"{logs_path}/{time.strftime('%Y.%m.%d')}.log", mode="a", encoding="utf-8"),
		logging.StreamHandler(),
	]:
		handler.setLevel(loggingLevel)
		handler.addFilter(IgnoreFilter(ignored))
		handler.setFormatter(formatter)
		logger.addHandler(handler)

	return logger
