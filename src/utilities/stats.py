import asyncio
import os
from datetime import datetime
from typing import NamedTuple

import psutil

from utilities.misc import exec


class Stats(NamedTuple):
	cpu: float
	ram: float
	last_updated: datetime


stats = Stats(0.0, 0.0, datetime.now())


async def system_monitor_task():
	global stats
	process = psutil.Process(os.getpid())

	while True:
		cpu_usage = await asyncio.to_thread(process.cpu_percent, interval=5)
		ram_usage = process.memory_percent()

		stats = Stats(cpu_usage, ram_usage, datetime.now())


def get_stats():
	return stats


class Version(NamedTuple):
	commit: str
	commit_long: str
	last_updated_at: datetime
	tag: str | None


def git_log() -> Version:
	fmt = "%h/%H/%ct"
	output = exec(["git", "log", "-1", f"--pretty={fmt}", "--no-patch"]).strip().split("/")
	tag = exec(["git", "describe", "--tags", "--abbrev=0"]).strip()
	return Version(output[0], output[1], datetime.fromtimestamp(float(output[2])), tag if tag != "" else None)


current_version: Version = git_log()


def get_version():
	global current_version
	if not current_version:
		current_version = git_log()
	return current_version


def get_current_branch() -> str:
	return exec(["git", "branch", "--show-current"]).strip()