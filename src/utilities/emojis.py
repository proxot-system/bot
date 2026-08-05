import re
from traceback import print_exc
from typing import Any, Literal, TypedDict
from urllib.parse import urlencode

from termcolor import colored
from yaml import safe_load

from utilities.config import get_config
from utilities.source_watcher import all_of, filter_file_suffix, filter_path, subscribe


class ProgressBar(TypedDict):
	empty: dict[Literal["start", "middle", "end"], str]
	filled: dict[Literal["start", "middle", "end"], str]


class BadgeTiers(TypedDict):
	normal: str
	bronze: str
	silver: str
	gold: str
	digital: str

SquareTypes = Literal[
	"barrens",
	"glen",
	"wm",
	"null",
	"red",
]
Icons = Literal[
	"loading",
	"wool",
	"sun",
	"inverted_clover",
	"capsule",
	"jam",
	"sleep",
	"refresh",
	"penguin",
]
PancakeTypes = Literal["normal", "golden", "glitched"]
TreasureTypes = Literal["amber", "bottle", "card", "clover", "die", "journal", "pen", "shirt", "sun"]
BadgeNames = Literal["shattered_sun", "wool", "sun", "remote"]


class Emojis(TypedDict):
	icons: dict[Icons, str]
	pancakes: dict[PancakeTypes, str]
	treasures: dict[TreasureTypes, str]
	progress_bars: dict[Literal["square", "round"], ProgressBar]
	badges: dict[BadgeNames, BadgeTiers]
	squares: dict[SquareTypes, tuple[str, str]]


def flatten_emojis(data: dict[str, Any], parent_key: str = "") -> dict[str, str]:
	items: list[tuple[str, str]] = []
	for k, v in data.items():
		key = f"{parent_key}.{k}" if parent_key else k
		if isinstance(v, dict):
			items.extend(flatten_emojis(v, key).items())
		elif isinstance(v, str):
			items.append((key, v))
	return dict(items)


def unflatten_emojis(flat_data: dict[str, str]) -> dict[str, Any]:
	unflattened: dict[str, Any] = {}
	for flat_key, value in flat_data.items():
		keys = flat_key.split(".")
		d = unflattened
		for key in keys[:-1]:
			if key not in d:
				d[key] = {}
			d = d[key]
		d[keys[-1]] = value
	return unflattened


def minify_emoji_names(data: Any) -> Any:
	if isinstance(data, dict):
		return {key: minify_emoji_names(value) for key, value in data.items()}
	elif isinstance(data, str):
		# replaces all names with "i" for more message content space
		return re.sub(r"(?<=[:])\w+(?=:\d)", "i", data)
	return data


def make_emoji_cdn_url(
	emoji: str | None = None,
	size: int | None = 4096,  # Passing None will make discord pick the resolution automatically
	quality: str = "lossless",
	emoji_id: str | None = None,
	name: str | None = None,
	is_animated: bool = False,
	filetype: Literal["png", "gif", "webp", "jpeg", "jpg"] | None = None,
) -> str:
	"""Make a discord cdn url for a custom emoji (out of an emoji, or manual. prioritizes 'emoji' if passed)"""
	if not emoji and not emoji_id:
		raise ValueError("No emoji passed (pass either 'emoji', or 'emoji_id' argument)")

	emoji_name = name
	animated = is_animated

	if emoji:
		match = re.match(r"<(a?):([a-zA-Z0-9_]+):([0-9]+)>", emoji)
		if not match:
			raise ValueError(f"Invalid emoji format for: {emoji}")

		is_animated_str, emoji_name, emoji_id = match.groups()
		animated = is_animated_str == "a"

	if not emoji_id:
		raise ValueError("Idk what the emoji id is")
	if filetype is None:
		filetype = "gif" if animated else "png"
	params = {"quality": quality, "animated": animated}
	if size:
		params["size"] = str(size)
	if emoji_name:
		params["name"] = emoji_name

	query_string = urlencode(params)

	return f"https://cdn.discordapp.com/emojis/{emoji_id}.{filetype}?{query_string}"


def load_emojis() -> Emojis:
	with open(get_config("paths.emojis"), "r") as f:
		emojis_data = safe_load(f)
		return minify_emoji_names(emojis_data)


emojis: Emojis = load_emojis()
emoji_subs = []


def on_emojis_update(callback):
	emoji_subs.append(callback)

	def unsubscribe():
		if callback in emoji_subs:
			emoji_subs.remove(callback)
		else:
			raise ValueError("Subscription was already removed before.")

	return unsubscribe


def update_emojis(flat_key, emoji_value: str | None = None):
	global emojis
	keys = flat_key.split(".")
	current_dict = emojis
	for part in keys[:-1]:
		current_dict.setdefault(part, {})

	if emoji_value is None:
		if keys[-1] in current_dict:
			del current_dict[keys[-1]]
	else:
		current_dict[keys[-1]] = emoji_value


def on_file_update(path):
	global emojis
	print(f"{colored('─ Reloading emojis', 'yellow')}", end=" ─ ─ ─ ")
	old_emojis = emojis
	try:
		new_emojis = load_emojis()
	except BaseException as e:
		print(colored(" FAILED", "red"))
		print_exc()
		from extensions.events.readylogger import ReadyLogsEvents

		err_msg = str(e)
		ReadyLogsEvents.queue(lambda channel: channel.send(content=f"## Failed to reload emojis\n{err_msg}"))
		return

	old_flat = flatten_emojis(dict(old_emojis))
	new_flat = flatten_emojis(dict(new_emojis))
	changes = []
	for key in [key for key in old_flat if key not in new_flat]:
		# removed
		changes.append(f"-{key}")
		update_emojis(key)
	for key in [key for key in new_flat if key not in old_flat]:
		# added
		changes.append(f"+{key}")
		update_emojis(key, emoji_value=new_flat[key])
	for key in [key for key in new_flat if key in old_flat and new_flat[key] != old_flat[key]]:
		# modified
		changes.append(f"*{key}")
		update_emojis(key, emoji_value=new_flat[key])
	for callback in emoji_subs:
		callback(new_emojis)
	print("done.", "No changes." if len(changes) == 0 else f"Changes: {', '.join(changes)}")


subscribe(all_of(filter_path(get_config("paths.emojis")), filter_file_suffix((".yml"))), on_file_update)
