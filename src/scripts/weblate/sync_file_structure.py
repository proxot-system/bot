import os
from pathlib import Path

from utilities.config import get_config

LOCALES_ROOT = Path(get_config("paths.localization.root"))
SOURCE_LOCALE = get_config("localization.sourceLocale")
SOURCE_PATH = LOCALES_ROOT / SOURCE_LOCALE


def run():
	if not SOURCE_PATH.exists():
		print(f"Error: Source path {SOURCE_PATH} not found.")
		return

	target_locales = [d.name for d in LOCALES_ROOT.iterdir() if d.is_dir() and d.name != SOURCE_LOCALE]

	if not target_locales:
		print("No target locales found to sync to.")
		return

	for root, dirs, files in os.walk(SOURCE_PATH):
		relative_root = Path(root).relative_to(SOURCE_PATH)

		for locale in target_locales:
			target_lang_root = LOCALES_ROOT / locale
			target_dir = target_lang_root / relative_root

			if not target_dir.exists():
				target_dir.mkdir(parents=True, exist_ok=True)
				print(f"  [DIR] Created {target_dir}")

			for file in files:
				target_file = target_dir / file

				if not target_file.exists():
					if target_file.suffix in (".yml", ".yaml"):
						with open(target_file, "w", encoding="utf-8") as f:
							f.write("")
					else:
						target_file.touch()

					print(f"  [FILE] Created {locale / relative_root / file}")

	print("\nDone.")
