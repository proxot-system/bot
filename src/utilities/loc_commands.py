from itertools import chain

import aiohttp
import yaml
from interactions import Message
from termcolor import colored

from utilities.config import get_config
from utilities.localization.localization import local_override


async def execute_loc_command(message: Message):
	if message.author.bot:
		return

	if not message.content:
		return

	if str(message.author.id) not in list(chain(*get_config("localization.whitelist", typecheck=dict).values())):
		return

	prefix = get_config("dev.command-marker").split(".")

	if not (message.content[0] == prefix[0] and message.content[-1] == prefix[1]):
		return

	command_content = message.content[1:-1].strip()

	args = command_content.split(" ")

	subcommand_name = args[0]

	match subcommand_name:
		case "locale_update":
			...
		case "locale_override":
			return {}
			if not message.attachments:
				return await message.reply("`[ Please attach a locale file ]`")

			attachment = message.attachments[0]
			locale = attachment.filename.split(".yml")[0]
			if not locale or not attachment.filename.endswith(".yml"):
				return await message.reply("`[ Invalid filename ]`")
			if str(message.author.id) not in get_config(
				f"localizations.whitelist.{locale.strip('.[]')}", typecheck=list
			):
				return await message.reply("`[ You are not whitelisted for this locale ]`")
			try:
				async with aiohttp.ClientSession() as session:
					async with session.get(attachment.url) as response:
						if response.status != 200:
							return await message.reply(f"`[ Failed to download the file: HTTP {response.status} ]`")

						content = await response.text()

				parsed_data = yaml.safe_load(content)
				if parsed_data is None:
					raise ValueError("Couldn't read for some reason?")
				local_override(locale, parsed_data)

				return await message.reply(f"`[ Updated {locale} locale ]`")
			except yaml.YAMLError as e:
				return await message.reply(f"`[ YAML parsing error: {str(e)} ]`")
			except Exception as e:
				return await message.reply(f"`[ Unknown exception: {str(e)} ]`")

		case _:
			return {}
	formatted_command_content = command_content.replace("\n", "\n" + colored("│ ", "yellow"))
	if subcommand_name == "db":
		subcommand_name += " ─"

	print(
		f"{colored('┌ loc_commands', 'yellow')} ─ ─ ─ ─ ─ ─ ─ ─ {subcommand_name}\n"
		+ f"{colored('│', 'yellow')} {message.author.mention} ({message.author.username}) ran:\n"
		+ f"{colored('│', 'yellow')} {formatted_command_content}\n"
		+ f"{colored('└', 'yellow')} ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─"
	)
