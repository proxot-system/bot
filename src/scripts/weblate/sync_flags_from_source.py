import asyncio
import os
import re
from pathlib import Path
from typing import Dict, Optional

import aiohttp

from utilities.config import get_config

WEBLATE_API_TOKEN = os.environ.get("WEBLATE_TOKEN", get_config("localization.weblateToken"))
WEBLATE_URL = os.environ.get("WEBLATE_URL", "https://translate.theworldmachine.xyz")
PROJECT_SLUG = os.environ.get("PROJECT_SLUG", "discord-bot")
LANGUAGE_CODE = os.environ.get("LANGUAGE_CODE", "en_GB")

LOCALES_ROOT = Path(get_config("paths.localization.root"))
SOURCE_LOCALE = get_config("localization.sourceLocale")
SOURCE_PATH = LOCALES_ROOT / SOURCE_LOCALE

SEMAPHORE = asyncio.Semaphore(15)


async def parse_flags_from_file(file_path: Path) -> Dict[str, str]:
	path_at_indent: Dict[int, str] = {}
	results: Dict[str, str] = {}
	pending_flags: Optional[str] = None

	if not file_path.exists():
		return {}

	with open(file_path, "r", encoding="utf-8") as f:
		lines = f.readlines()

	for line in lines:
		stripped = line.strip()
		if not stripped:
			continue

		indent = len(line) - len(line.lstrip(" "))
		flag_match = re.search(r"#\s*weblate-flags:\s*(.*)", stripped)

		if flag_match:
			raw_content = flag_match.group(1).split(",")
			clean_flags = [f.strip() for f in raw_content if f.strip()]
			pending_flags = ",".join(clean_flags)
			continue

		if ":" in stripped and not stripped.startswith("#"):
			key = stripped.split(":", 1)[0].strip()
			levels_to_remove = [i for i in path_at_indent if i >= indent]
			for level in levels_to_remove:
				del path_at_indent[level]

			path_at_indent[indent] = key
			sorted_indents = sorted(path_at_indent.keys())
			full_key = "->".join([path_at_indent[i] for i in sorted_indents])

			if pending_flags:
				results[full_key] = pending_flags
				pending_flags = None
		elif not stripped.startswith("#"):
			pending_flags = None

	return results


def get_component_slug(relative_path: Path) -> str:
	component_part = str(relative_path.with_suffix("")).replace("\\", "/")
	if component_part in ["main", "facepics"]:
		return component_part

	clean_part = component_part.replace("/", "-")
	return clean_part.lower()


async def clear_translations_for_key(session: aiohttp.ClientSession, comp_slug: str, key: str):
	"""
	Finds all translations for a specific key (excluding the source language)
	and clears their content.
	"""
	search_url = f"{WEBLATE_URL}/api/units/"
	params = {
		"q": f'key:"{key}" AND component:{comp_slug} AND NOT language:{LANGUAGE_CODE}',
		"project": PROJECT_SLUG,
	}

	try:
		async with session.get(search_url, params=params) as response:
			if response.status != 200:
				return

			data = await response.json()
			if data["count"] == 0:
				return

			for unit in data["results"]:
				unit_id = unit["id"]  # I SET FIIIRE TO THE RAIN
				if unit["target"]:
					update_url = f"{WEBLATE_URL}/api/units/{unit_id}/"
					async with session.patch(update_url, json={"target": ""}) as patch_res:
						if patch_res.status in (200, 204):
							print(f"  - 🧹 [{comp_slug}]: Cleared translation for '{key}' in {unit['language_code']}")
	except Exception as e:
		print(f"  - ❌ Error clearing translations for '{key}': {e}")


async def update_unit(session: aiohttp.ClientSession, comp_slug: str, key: str, flags: str):
	async with SEMAPHORE:
		search_url = f"{WEBLATE_URL}/api/units/"
		params = {
			"q": f'key:"{key}" AND language:{LANGUAGE_CODE} AND component:{comp_slug}',
			"project": PROJECT_SLUG,
		}

		try:
			async with session.get(search_url, params=params) as response:
				if response.status != 200:
					print(f"  - ❌ Error fetching '{key}' [{comp_slug}]: {response.status}")
					return

				data = await response.json()
				if data["count"] == 0:
					return

				unit = data["results"][0]
				source_unit_url = unit.get("source_unit")
				target_id = source_unit_url.strip("/").split("/")[-1] if source_unit_url else unit["id"]

				update_url = f"{WEBLATE_URL}/api/units/{target_id}/"
				async with session.patch(update_url, json={"extra_flags": flags}) as patch_res:
					if patch_res.status in (200, 204):
						print(f"  - ✅ [{comp_slug}]: Updated flags for '{key}'")
					else:
						print(f"  - ❌ [{comp_slug}]: Failed patch '{key}', {patch_res.status}")

				if "read-only" in flags:
					await clear_translations_for_key(session, comp_slug, key)

		except Exception as e:
			print(f"  - ❌ [{comp_slug}]: Unexpected error for '{key}', {e}")


async def run():
	if not WEBLATE_API_TOKEN or WEBLATE_API_TOKEN == "..." or WEBLATE_API_TOKEN == "YOUR_WEBLATE_API_TOKEN":
		print("Error: WEBLATE_TOKEN not set or invalid.")
		return

	if not SOURCE_PATH.exists():
		print(f"Error: Source path {SOURCE_PATH} not found.")
		return

	files = list(SOURCE_PATH.rglob("*.yml"))
	tasks = []

	async with aiohttp.ClientSession(headers={"Authorization": f"Token {WEBLATE_API_TOKEN}"}) as session:
		for file_path in files:
			rel_path = file_path.relative_to(SOURCE_PATH)
			comp_slug = get_component_slug(rel_path)

			string_flags = await parse_flags_from_file(file_path)
			if not string_flags:
				continue

			print(f"Queueing updates for {rel_path}...")
			for key, flags in string_flags.items():
				tasks.append(update_unit(session, comp_slug, key, flags))

		if tasks:
			print(f"Executing {len(tasks)} tasks...")
			await asyncio.gather(*tasks)

	print("\nDone.")
