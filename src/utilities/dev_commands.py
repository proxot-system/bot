import io
import json
import re
import sys
import time
import traceback as tb
from asyncio import iscoroutinefunction
from dataclasses import is_dataclass
from datetime import datetime

import yaml
from aioconsole import aexec
from interactions import Embed, Member, Message
from termcolor import colored

import utilities.database.main as main
import utilities.database.schemas as schemas
from utilities.config import get_config, on_prod
from utilities.emojis import emojis
from utilities.localization.formatting import fnum
from utilities.message_decorations import Colors
from utilities.misc import shell
from utilities.shop.fetch_items import fetch_treasure
from utilities.shop.fetch_shop_data import get_shop_data

ansi_escape_pattern = re.compile(r"\033\[[0-9;]*[A-Za-z]")


def get_collection(collection: str, _id: str):
	try:
		found = getattr(schemas, collection)
	except:
		found = None
	if found is None or is_dataclass(found) or (hasattr(found, "__name__") and found.__name__ == "StatUpdate"):
		raise ValueError(
			"Invalid collection name, valid one's: "
			+ ", ".join(
				filter(
					lambda a: (
						is_dataclass(getattr(schemas, a))
						or (hasattr(getattr(schemas, a), "__name__") and getattr(schemas, a).__name__ == "StatUpdate")
					),
					dir(schemas),
				)
			)
		)
	return found(_id)


class CapturePrints:
	def __init__(self, output_buffer):
		self.output_buffer = output_buffer
		self.bogos_printed = False
		self.print = self._capture_print

	def __enter__(self):
		return self

	def _capture_print(self, *args, sep=" ", end="\n", file=None, flush=False):
		self.bogos_printed = True
		output = sep.join(map(str, args))
		self.output_buffer.write(output + end)

		if flush and file is not None:
			file.flush()

	def __exit__(self, exc_type, exc_val, exc_tb):
		pass


async def redir_prints(method, code, locals=None, globals=None):
	if locals is None:
		locals = {}
	output_buffer = io.StringIO()
	with CapturePrints(output_buffer) as cp:
		locals["print"] = cp.print

		if iscoroutinefunction(method):
			await method(code, locals)
		else:
			method(code, globals, locals)
	if cp.bogos_printed:
		return cp.output_buffer.getvalue()


command_marker = get_config("dev.command-marker")
if on_prod:
	_pm = get_config("bot.prod.command-marker", ignore_None=True)
	command_marker = _pm if _pm is not None else command_marker


async def execute_dev_command(message: Message):
	try:
		return await _execute_dev_command(message)
	except Exception as e:
		result = f"Raised an exception when processing command: {str(e)}"
		lines = []
		raw_tb = tb.format_exc(chain=True)
		print(raw_tb)
		for line in raw_tb.split("\n"):
			lines.append(line)
		lines.pop(0)
		result = "\n".join(lines)
		return await message.reply(
			embeds=Embed(
				color=Colors.BAD,
				description=f"\n```py\n{result[0:3900].replace('```', '` ``')}```",
			)
		)


async def _execute_dev_command(message: Message):
	if not message.content:
		return

	if message.author.bot and str(message.author.id) not in get_config("dev.whitelist", typecheck=list):
		return

	if str(message.author.id) not in get_config("dev.whitelist", typecheck=list):
		return

	client = message.client
	prefix = command_marker.split(".")

	if not (message.content[0] == prefix[0] and message.content[-1] == prefix[1]):
		return

	command_content = message.content[1:-1].strip()

	args = command_content.split(" ")

	subcommand_name = args[0]

	formatted_command_content = command_content.replace("\n", "\n" + colored("│ ", "yellow"))
	print(
		f"{colored('┌ dev_commands', 'yellow')} ─ ─ ─ ─ ─ ─ ─ ─ {subcommand_name + (' ─' if subcommand_name == 'db' else '')}\n"
		+ f"{colored('│', 'yellow')} {message.author.mention} ({message.author.username}) ran:\n"
		+ f"{colored('│', 'yellow')} {formatted_command_content}\n"
		+ f"{colored('└', 'yellow')} ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─"
	)

	match subcommand_name:
		case "bot":
			subcase = args[1]
			match subcase:
				case "refresh":
					try:
						extension = args[2]
					except IndexError:
						return await message.reply('[ This command expects an extension to refresh, or "all" ]')
					if extension == "all":
						message.content = "{eval ```py\nload_commands(client, unload=True, print=print)\n```}"
						return await execute_dev_command(message)
					else:
						msg = await message.reply(f"[ Working... {emojis['icons']['loading']} ]")
						try:
							client.reload_extension(extension)
						except Exception as e:
							await message.reply(f"`[ {e} ]`")
						return await msg.edit(content=f"[ Reloaded {extension} ]")
				case "sync_commands":
					msg = await message.reply(f"[ Synchronizing commands... {emojis['icons']['loading']} ]")
					await client.synchronise_interactions(delete_commands=True)
					return await msg.edit(content="[ Synchronized ]")
				case "shell":
					msg = await message.reply(f"[ Running... {emojis['icons']['loading']} ]")
					parse = " ".join(args).split(args[1])
					if len(parse) < 1:
						return await msg.edit(
							content="[ No command passed. This command expects a command to execute in the terminal, e.g. `[bot shell echo meow]` ]"
						)
					output = shell(parse[1])
					return await msg.edit(content=f"[ Done ]\n```bash\n{output}```")
				case "log":
					text_to_log = command_content.split(args[0] + " log ", maxsplit=1)
					from extensions.events.Ready import ReadyEvent

					if len(text_to_log) == 1:
						out = await ReadyEvent.log(lambda channel: channel.send(content=f"<@{message._author_id}>"))
						return await message.reply(f"[ logs u {out.jump_url} ]")
					out = await ReadyEvent.log(lambda channel: channel.send(content=text_to_log[1]))
					return await message.reply(f"[ logged {out.jump_url} ]")
				case _:
					return await message.reply("Available subcommands: `refresh` / `sync_commands` / `shell` / `log`")
		case "inventory":
			subcase = args[1]
			match subcase:
				case "sell":
					try:
						userid = args[2]
						target_items_raw = args[3]
					except IndexError:
						return await message.reply(
							"`[ Usage: [inventory sell {userid} all] or [inventory sell {userid} comma,separated,items] ]`"
						)

					user_data: schemas.UserData = await schemas.UserData(_id=userid).fetch()
					daily_shop = await get_shop_data()
					all_treasures = await fetch_treasure()
					stock_price = daily_shop.stock.price

					before_wool = user_data.wool
					before_treasures = dict(user_data.owned_treasures)

					if target_items_raw.lower() == "all":
						treasures_to_sell = list(user_data.owned_treasures.keys())
					else:
						treasures_to_sell = [x.strip() for x in target_items_raw.split(",")]

					wool_gained = 0
					sold_details = []

					for tid in treasures_to_sell:
						if tid not in before_treasures or before_treasures[tid] <= 0:
							continue
						if tid not in all_treasures:
							continue

						amount = before_treasures[tid]
						price_per_item = int(all_treasures[tid]["price"] * stock_price)
						total_price = price_per_item * amount

						wool_gained += total_price
						del user_data.owned_treasures[tid]

						sold_details.append(f"**{tid}**: {amount} -> 0 (+{total_price} {emojis['icons']['wool']})")

					if wool_gained > 0:
						await user_data.update(owned_treasures=user_data.owned_treasures)
						await user_data.manage_wool(wool_gained)

					after_wool = user_data.wool

					desc = [f"**Wool:** {before_wool} -> {after_wool} (+{wool_gained})\n", "**Treasures Sold:**"]
					if not sold_details:
						desc.append("None")
					else:
						desc.extend(f"- {detail}" for detail in sold_details)

					embed = Embed(title=f"Inventory update for {userid}", color=Colors.GREEN, description="\n".join(desc))
					return await message.reply(embeds=embed)
				case _:
					return await message.reply("`[ Available subcommands: sell ]`")
		case "eval":
			code = command_content.split("eval ")
			referenced_message = message.get_referenced_message()
			reply_content = referenced_message.content if referenced_message and referenced_message.content else None

			if len(code) == 1 and reply_content and reply_content.startswith("```py\n"):
				code = reply_content
			elif len(code) > 1:
				code = command_content.split("eval ")[1]
			else:
				code = ""

			if code.startswith("```py\n") and code.endswith("```"):
				code = code[5:-3].strip()
				if "await" in code:
					method = "aexec"
				else:
					method = "exec"
			else:
				method = "eval"

			result = None
			runtime = None
			start_time = time.perf_counter()
			state = {
				"asnyc_warn": False,
				"strip_ansi_sequences": True,
				"raisure": False,
			}
			try:
				match method:
					case "exec":
						result = await redir_prints(exec, code, locals(), globals())
					case "aexec":
						result = await redir_prints(aexec, code, locals())
					case "eval":
						if len(code) == 0:
							raise BaseException("no code provided")
						result = eval(code, globals(), locals())
				end_time = time.perf_counter()
			except Exception:
				end_time = time.perf_counter()
				state["raisure"] = True
				exc_type, exc_value, exc_tb = sys.exc_info()

				if str(exc_value) in (
					"py codeblock is required here",
					"no code provided",
				):
					result = str(exc_value)
				if method == "eval":
					result = str(exc_value)
				else:
					lines = []
					raw_tb = tb.format_exc(chain=True)
					print(raw_tb)

					for line in raw_tb.split("\n"):
						lines.append(
							line.replace('  File "<aexec>", ', " - at ")
							.replace('  File "<string>", ', " - at ")
							.replace(", in __corofn", "")
							.replace(", in <module>", "")
						)
					lines.pop(0)
					result = "\n".join(lines)
					result_tmp = result.split(" in redir_prints\n    method(code, globals, locals)")
					if len(result_tmp) != 2:  # aexec
						state["asnyc_warn"] = True
						result_tmp = result.split(" new_local = await coro\n                        ^^^^^^^^^^\n")
					result = result_tmp[1] if len(result_tmp) > 1 else result

			runtime = (end_time - start_time) * 1000

			async def handle_reply(runtime, result, note=""):
				desc = f"-# Runtime: {fnum(runtime)} ms{note}"
				if state["asnyc_warn"]:
					desc += "\n-# All line numbers are offset by +1 cuz of await"
				if result is None and method in ("aexec", "exec"):
					desc += "\n-# Nothing was printed"
				else:
					desc += f"\n```py\n{str(result).replace('```', '` ``')}```"

				color = Colors.DEFAULT
				if state["raisure"]:
					color = Colors.BAD
				return await message.reply(embeds=Embed(color=color, description=desc))

			try:
				if isinstance(result, str) and state["strip_ansi_sequences"]:
					result = ansi_escape_pattern.sub("", result)
				return await handle_reply(runtime, result)
			except Exception as e:
				tb.print_exc()
				if "Description cannot exceed 4096 characters" in str(e):  # TODO: paging
					return await handle_reply(
						runtime,
						str(result)[0:3900],
						"\n-# Result too long to display, showing first 3900 characters",
					)
				else:
					result = f"Raised an exception when replying(WHAT did you do): {str(e)}"
					lines = []
					for line in tb.format_exc(chain=True).split("\n"):
						lines.append(line)
					lines.pop(0)
					result = "\n".join(lines)
					return await handle_reply(runtime, result)
		case "shop":
			items = await main.fetch_items()
			if not items:
				return await message.reply("`[ Failed to fetch shop from database ]`")
			shop = items["shop"]

			match args[1]:
				case "view":
					return await message.reply(
						f"```yml\n{yaml.dump(shop, default_flow_style=False, Dumper=yaml.SafeDumper)}```"
					)
				case "reset":
					try:
						await get_shop_data()
						return await message.reply("`[ Successfully reset shop ]`")
					except Exception as e:
						return await message.reply(f"`[ {e} ]`")
				case "update":
					try:
						target = args[2]
						val_raw = args[3]
					except IndexError:
						return await message.reply("`[ Usage: [shop update stock 0.5] or [shop update stock 0.5,1] ]`")

					if target == "stock":
						daily_shop = await get_shop_data()
						try:
							if "," in val_raw:
								p, v = map(float, val_raw.split(","))
								daily_shop.stock.price = p
								daily_shop.stock.value = v
							else:
								daily_shop.stock.price += float(val_raw)
						except ValueError:
							return await message.reply("`[ Invalid number format ]`")

						await main.update_shop(
							{
								"last_updated": daily_shop.last_updated,
								"backgrounds": daily_shop.background_stock,
								"treasures": daily_shop.treasure_stock,
								"motd": daily_shop.motd,
								"stock": {"price": daily_shop.stock.price, "value": daily_shop.stock.value},
							}
						)
						return await message.add_reaction("✅")
					else:
						return await message.reply("`[ Only 'stock' update is currently supported ]`")
				case _:
					return await message.reply("Available subcommands: `view` / `reset` / `update`")
		case "db":
			try:
				match args[1]:
					case "set":
						pattern = r"\{(?:[^{}]*|\{[^{}]*\})*\}"

						matches = re.findall(pattern, command_content)

						try:
							collection_name = args[2]
							_id = args[3]
						except:
							raise ValueError("[db set] expects 2 args: `collection_name` and `id`")
						str_data = matches[0]

						data = json.loads(str_data)

						collection = await get_collection(collection_name, _id).fetch()

						await collection.update(**data)

						return await message.reply("`[ Successfully updated ]`")
					case "view":
						try:
							collection_name = args[2]
							_id = args[3]
							value = args[4]
						except:
							raise ValueError("[db view] expects 3 args: `collection_name`, `id` and `value`")
						if collection_name == "shop":
							collection = await get_collection(collection_name, "0")
						else:
							collection = await get_collection(collection_name, _id).fetch()

						return await message.reply(f"`[ The value of {value} is {str(collection.__dict__[value])} ]`")
					case "view_all":
						try:
							collection_name = args[2]
							_id = args[3]
						except:
							raise ValueError("[db view] expects 2 args: `collection_name` and `id`")

						collection = await get_collection(collection_name, _id).fetch()

						return await message.reply(
							f"```yml\n{yaml.dump(main.to_dict(collection), default_flow_style=False, Dumper=yaml.SafeDumper)}```"
						)
					case "wool":
						try:
							_id = args[2]
							amount = int(args[3])
						except:
							raise ValueError("[db view] expects 2 args: `id` and numeric `amount`")

						collection: schemas.UserData = await schemas.UserData(_id).fetch()

						await collection.manage_wool(amount)

						return await message.reply(f"`[ Successfully modified wool, updated value is now {collection.wool} ]`")
					case _:
						return await message.reply("Available subcommands: `set` / `view` / `view_all` / `wool`")
			except Exception as e:
				tb.print_exc()
				await message.reply(f"``[ Error with command ({e}) ]``")
		case "util":
			subcase = args[1]
			match subcase:
				case "fakejoin":
					from interactions.api.events import MemberAdd

					user_id = args[2] if len(args) >= 3 else message.author.id
					guild_id = args[3] if len(args) == 4 else None
					if guild_id is None:
						if not message.guild:
							raise ValueError("[ [util fakejoin] expects all arguments in dms: `user_id` and `guild_id` ]")
						guild_id = message.guild.id

					guild = await client.fetch_guild(guild_id)
					if not guild:
						raise ValueError(f"Could not find the guild with ID: {guild_id}")

					member = await guild.fetch_member(user_id)
					if not member:
						user = await client.fetch_user(user_id)
						if user:
							print(f"Could not find member with ID: {user_id} in the specified guild.")
						else:
							raise ValueError(f"Could not find User with ID {user_id}")
						member = Member.from_dict(
							{
								"premium_since": None,
								"pending": False,
								"nick": None,
								"mute": False,
								"joined_at": datetime.now(),
								"flags": 0,
								"deaf": False,
								"communication_disabled_until": None,
								"banner": user.banner,
								"avatar": user.avatar,
								"guild_id": guild.id,
								"id": user.id,
								"bot": user.bot,
								"role_ids": [],
							},
							client,
						)
					event = MemberAdd(guild.id, member, bot=client)
					client.dispatch(event)
					return await message.reply(f"[ Dispatched {event} ]")
				case _:
					return await message.reply("Available subcommand: `fakejoin`")
		case "locale_override":
			return
		case _:
			return {}
