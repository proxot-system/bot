from pathlib import Path
from traceback import print_exc
from typing import Any, Literal, Type, TypeVar, overload

from pkl import PklError
from pkl import load as load_piquel
from termcolor import colored

from utilities.misc import rabbit

bcpath = Path("config.overrides.pkl")
try:
	config: Any = load_piquel(bcpath)
	print("Loaded configuration")
except PklError:  #
	print_exc()
	print(
		colored(
			f"─ config file at '{bcpath.resolve()}' is missing or failed to load.\nAre you sure you set it up correctly?",
			"yellow",
		)
	)
	exit(1)

C = TypeVar("C")


# all of these overloads were made by google gemini bytheway i'm too lazy to learn how this works
@overload
def get_config(path: str, *, raise_on_not_found: bool = True, ignore_None: Literal[False] = False) -> str: ...


@overload
def get_config(path: str, *, raise_on_not_found: bool = True, ignore_None: Literal[True]) -> str | None: ...


@overload
def get_config(
	path: str,
	*,
	typecheck: Type[C],
	raise_on_not_found: bool = True,
	ignore_None: Literal[False] = False,
) -> C: ...


@overload
def get_config(
	path: str,
	*,
	typecheck: Type[C],
	raise_on_not_found: bool = True,
	ignore_None: Literal[True],
) -> C | None: ...


def get_config(
	path: str,
	*,
	typecheck: Type[C] | None = None,
	raise_on_not_found: bool = True,
	ignore_None: bool = False,
) -> C | str | None:
	"""
	Retrieves a value from the configuration file.

	Args:
	    path: The dot-separated path to the configuration value.
	    typecheck: The expected type of the value. If provided, the function will validate
	               the type and return it, or raise a TypeError. If omitted, the value
	               is returned as a string.
	    raise_on_not_found: If True (default), raises an error if the path is not found.
	    ignore_None: If True, suppresses errors for missing paths and returns None instead.
	                 This overrides `raise_on_not_found`.
	"""
	should_raise = raise_on_not_found and not ignore_None
	return_none = ignore_None

	res = rabbit(
		config,
		path,
		raise_on_not_found=should_raise,
		return_None_on_not_found=return_none,
		_error_message="Configuration does not have [path]",
		use_attr_access=True,
	)

	if res is None:
		return None

	if typecheck is None:
		return str(res)

	if not isinstance(res, typecheck):
		raise TypeError(f"Configuration value for '{path}' has type {type(res)}, but expected {typecheck.__name__}")

	return res


cl = get_config("configCheckLevel", typecheck=int, ignore_None=True)
if cl is not None:
	to_check: list[tuple[str, bool]] = [
		("bot.token", True),
		("database.connection.password", True),
		("localization.sourceLocale", True),
		("bot.rolling.avatar", False),
		("bot.rolling.status", False),
		("bot.rolling.interval", False),
		("music.spotify.secret", False),
		("music.spotify.id", False),
	]
	for key, required in to_check:
		got = get_config(key, ignore_None=True)
		if got is not None:
			continue
		if required:
			print(colored("─ config key ") + colored(key, "cyan") + colored(" is required", "red"))
			if cl <= 1:
				exit(1)
		else:
			if cl <= 3:
				print(colored("─ config key ") + colored(key, "cyan") + colored(" is missing", "yellow"))
			if cl <= 2:
				exit(1)


debug = get_config("debug", typecheck=bool, ignore_None=True)
debug_override = None

def debugging():
	global debug_override
	return debug_override if debug_override is not None else debug


def setd(value: bool):
	global debug_override
	debug_override = value


def get_token() -> str:
	return get_config("bot.token")
