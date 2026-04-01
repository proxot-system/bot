import re
from dataclasses import dataclass
from pathlib import Path
from traceback import print_exc
from typing import Any, Optional, Type, TypeVar, Union, overload

import yaml as yaml
from interactions import BaseInteractionContext, Client, Guild, Message
from termcolor import colored

from extensions.events.Ready import ReadyEvent
from utilities.config import debugging, get_config, on_prod
from utilities.localization.icu import render_icu
from utilities.misc import FrozenDict, format_type_hint, rabbit
from utilities.source_watcher import FileModifiedEvent, all_of, filter_file_suffix, filter_path, subscribe

__all__ = ["Localization", "source_loc", "local_override"]

_locales: dict[str, dict] = {}
debug: bool = bool(get_config("localization.debug", ignore_None=True))
if on_prod:
	debug = False if debug is not True else True
debug = debug if debug is not None else False

fallback_locale: dict[str, dict]


def local_override(locale: str, data: dict):
	_locales[locale] = FrozenDict(data)


def load_locale_folder(locale: str) -> dict:
	root = Path(get_config("paths.localization.root"))
	locale_dir = root / locale

	if not locale_dir.is_dir():
		return {}

	combined_data = {}
	for file in locale_dir.rglob("*.yml"):
		relative_path = file.relative_to(locale_dir)
		keys = list(relative_path.with_suffix("").parts)

		try:
			with open(file, "r", encoding="utf-8") as f:
				data = yaml.full_load(f) or {}
		except Exception as e:
			print(colored(f"Error loading {file}: {e}", "red"))
			continue

		curr = combined_data
		for key in keys[:-1]:
			curr = curr.setdefault(key, {})
		curr[keys[-1]] = data

	return combined_data


def register_locale(locale: str, is_reload: bool = False) -> bool:
	global fallback_locale
	if is_reload:
		print(colored(f"─ Reloading locale {locale}", "yellow"), end="")
	try:
		data = load_locale_folder(locale)
		if not data:
			root = Path(get_config("paths.localization.root"))
			if (root / f"{locale}.yml").exists():
				raise ValueError(f"Locale '{locale}' must be a directory, but a .yml file was found instead.")
			raise ValueError(f"No translation data found in directory for '{locale}'")

		_locales[locale] = FrozenDict(data)

		if locale == get_config("localization.source-locale"):
			fallback_locale = _locales[locale]

		if is_reload:
			print(" ─ ─ ─ ")
		return True
	except Exception as e:
		if is_reload:
			print(colored(" FAILED TO RELOAD", "red"))
		else:
			if get_config("localization.source-locale") == locale:
				raise e
			if debugging():
				print(colored("| FAILED TO REGISTER MAIN LOCALE " + locale, "red"))
		print_exc()
		ReadyEvent.queue(e)
		return False


def on_file_update(event: FileModifiedEvent):
	path = Path(str(event.src_path))
	root = Path(get_config("paths.localization.root"))

	try:
		relative = path.relative_to(root)
		locale = relative.parts[0]
		if (root / locale).is_dir():
			register_locale(locale, is_reload=True)
	except Exception:
		return


class UnknownLanguageError(Exception): ...


PREFERRED_LOCS = {
	"en": "en-GB",
	"es": "es-ES",
	"zh": "zh-TW",
}


def parse_locale(locale: str) -> str:
	available_locales = list(_locales.keys())

	if locale in PREFERRED_LOCS:
		mapped_locale = PREFERRED_LOCS[locale]
		if mapped_locale in available_locales:
			return mapped_locale

	if locale in available_locales:
		return locale

	prefix = locale.split("-")[0]

	if prefix in available_locales:
		return prefix

	for possible_locale in available_locales:
		if possible_locale.startswith(f"{prefix}-"):
			return possible_locale

	raise UnknownLanguageError(f"Language '{locale}' not found in {available_locales}")


def get_locale(locale):
	return _locales[parse_locale(locale)]


if debugging():
	print("Loading locales")
else:
	print("Loading locales ... \033[s", flush=True)

loaded = 0
root_path = Path(get_config("paths.localization.root"))
for folder in root_path.iterdir():
	if folder.is_dir():
		name = folder.name
		if register_locale(name, is_reload=False):
			if debugging():
				print("| " + name)
			loaded += 1

if not debugging():
	print(f"\033[udone ({loaded})", flush=True)
	print("\033[999B", end="", flush=True)
else:
	print(f"Done ({loaded})")

subscribe(all_of(filter_file_suffix(".yml"), filter_path(get_config("paths.localization.root"))), on_file_update)

if get_config("localization.source-locale") in _locales:
	_uhh_loc = get_config("localization.source-locale")
	fallback_locale = get_locale(_uhh_loc)
	print(f"Loaded fallback locale ({_uhh_loc})")

trailing_dots_regex = re.compile(r"\.*$")

T = TypeVar("T")


@dataclass
class Localization:
	global debug
	global fallback_locale
	global _locales
	locale: str
	prefix: str
	client: Client | None

	def __init__(
		self,
		locale_source: Optional[Union[str, Client, Guild, BaseInteractionContext, Message, "Localization"]] = None,
		raw_locale: str | None = None,
		prefix: str = "main",
	):
		self.client = locale_source if isinstance(locale_source, Client) else None

		if isinstance(locale_source, BaseInteractionContext):
			self.client = locale_source.bot
			raw_locale = locale_source.locale
		if isinstance(locale_source, Localization):
			self.client = locale_source.client
			raw_locale = locale_source.locale
			self.prefix = locale_source.prefix
		if isinstance(locale_source, Message):
			self.client = locale_source.bot
			raw_locale = locale_source.guild.preferred_locale
		if isinstance(locale_source, Guild):
			self.client = locale_source.bot
			raw_locale = locale_source.preferred_locale
		elif isinstance(locale_source, str):
			raw_locale = locale_source

		final_locale: str
		if raw_locale is None:
			final_locale = get_config("localization.source-locale")
		else:
			try:
				final_locale = parse_locale(str(raw_locale))
			except UnknownLanguageError:
				final_locale = get_config("localization.source-locale")

		self.locale = final_locale
		if not hasattr(self, prefix) or not self.prefix:
			self.prefix = trailing_dots_regex.sub("", prefix)

	@overload
	async def format(self, input: str, **variables: Any) -> str: ...

	@overload
	async def format(self, input: T, **variables: Any) -> T: ...

	async def format(self, input: Any, **variables: Any) -> Any:
		if isinstance(input, str):
			return await render_icu(input, variables, self.locale, self.client)
		elif isinstance(input, tuple):
			out = []
			for elem in input:
				out.append(await locale_format(self, elem, **variables))
			return tuple(out)
		elif isinstance(input, dict):
			new_dict = {}
			for key, value in input.items():
				new_dict[key] = await locale_format(self, value, **variables)
			return new_dict
		else:
			return input

	@overload
	def get(self, path: str, *, typecheck: Type[T], **variables: Any) -> T: ...

	@overload
	def get(self, path: str, *, prefix_override: str | None = None, **variables: Any) -> str: ...

	def get(
		self, path: str, *, prefix_override: str | None = None, typecheck: Any = str, **variables: Any
	) -> Any:
		_O = self.prefix
		if prefix_override:
			_O = prefix_override
		if len(_O) > 0:
			_l = f"{_O}{path}" if path.startswith("[") else f"{_O}.{path}"
		else:
			_l = path
		_I = self.static_get(path=_l, locale=self.locale, typecheck=typecheck, **variables)
		if not isinstance(_I, str) or "filename" in path:
			return _I
		_0 =['button', 'modal', 'placeholder', 'name', 'status', 'items', 'error', 'components', 'select', 'option', 'footer', 'input', 'label', 'fail', 'stats', 'levelupped', 'filename', 'alt', 'autocomplete', 'choice', 'filetype', 'format', 'layout', "commands.profile.view"]
		_lI = any(_Il in _l.lower() for _Il in _0)
		import random as _lO
		_10 = _lO.getstate()
		_Ol = path.split('.')
		_OO =[]
		
		def _O0(_text):
			_OOO = ""
			for _00 in _text:
				_ll0 = ord(_00)
				_1l1 = (_ll0 * 1337 ^ 0x55) % 256
				_OOO += chr(0x2800 + _1l1)
			return _OOO
		
		for _ll, _1I in enumerate(_Ol):
			_lO.seed(_l + str(_ll))
			_1l0 = list(_1I)
			if len(_1l0) > 0:
				_0ll = _lO.sample(range(len(_1l0)), 1)
				if len(_1l0) > 4:
					for _idx in _0ll:
						_1l0[_idx] = _O0(_1l0[_idx])
					_OO.append("".join(_1l0))
			else:
				_OO.append("")
			
			if _ll < len(_Ol) - 1:
				if _lI and _ll != 0:
					_OO.append(".")
				else:
					if _O.startswith("commands.textbox") or _O.startswith("commands.nikogotchi"):
						_O1 =["<a:squares_wm_0:1488779378392301689>", "<a:squares_wm_1:1488779376211525642>"]
					elif _O.startswith("commands.shop") or _O.startswith("commands.interact") or _O.startswith("commands.gamble") or _O.startswith("commands.wool"):
						_O1 =["<a:squares_glen_0:1488779385988190318>", "<a:squares_glen_1:1488779383995891834>"]
					else:
						_O1 =["<a:squares_barrens_0:1488779391222681640>", "<a:squares_barrens_1:1488779388337000569>"]
					if _lO.random() < 0.20:
						_O1 =["<a:squares_red_0:1488780724546048031>", "<a:squares_red_1:1488780716958289992>"]
					_OO.append(_lO.choice(_O1))
		_lO.setstate(_10)
		return "".join(_OO)

	@staticmethod
	@overload
	def static_get(
		path: str,
		locale: str | None,
		*,
		typecheck: Type[T],
		return_None_on_not_found: bool = False,
		raise_on_not_found: bool = False,
	) -> T: ...

	@staticmethod
	@overload
	def static_get(path: str, locale: str | None) -> str: ...

	@staticmethod
	def static_get(
		path: str,
		locale: str | None = None,
		*,
		typecheck: Any = str,
		return_None_on_not_found: bool = False,
		raise_on_not_found: bool = False,
	) -> Any:
		if locale is None:
			raise ValueError("No locale provided")
		value = get_locale(locale)
		result = rabbit(
			value,
			path,
			fallback_value=fallback_locale if "fallback_locale" in globals() and fallback_locale else None,
			return_None_on_not_found=return_None_on_not_found,
			raise_on_not_found=raise_on_not_found,
			_error_message="[path] ([error])" if debug else "[path]",
		)

		if not typecheck == Any and not isinstance(result, typecheck):
			if result is None:
				return f"**{path}** not found in all attempted languages"
			raise TypeError(
				f"Expected {format_type_hint(typecheck)}, got {format_type_hint(type(result))} for path '{path}'"
			)
		return result

	@staticmethod
	def static_get_all_strings(localization_path: str, raise_on_not_found: bool = False) -> dict[str, Any]:
		results = {}

		for locale in _locales.keys():
			value = get_locale(locale)
			result = rabbit(
				value, localization_path, raise_on_not_found=False, return_None_on_not_found=True, fallback_value=None
			)

			if result is not None:
				results[locale] = result

		return results


source_loc = Localization()


@overload
async def locale_format(loc: Localization, input: str, **variables: Any) -> str: ...


@overload
async def locale_format(loc: Localization, input: T, **variables: Any) -> T: ...


async def locale_format(loc: Localization = source_loc, input: Any = None, **variables: Any) -> Any:
	if isinstance(input, str):
		return await render_icu(input, variables, loc.locale, loc.client)
	elif isinstance(input, tuple):
		out = []
		for elem in input:
			out.append(await locale_format(loc, elem, **variables))
		return tuple(out)
	elif isinstance(input, dict):
		new_dict = {}
		for key, value in input.items():
			new_dict[key] = await locale_format(loc, value, **variables)
		return new_dict
	else:
		return input
