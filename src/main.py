print("\033[999B", end="", flush=True)

from datetime import datetime
from logging import INFO

from termcolor import colored

from utilities.config import get_config, get_token
from utilities.logging import createLogger

logger = createLogger(__name__)
logger.log(INFO, colored("Starting The World Machine... 1/3\n\n", "light_cyan"))


import asyncio
import importlib
import sys

# Handled commands
VALID_COMMANDS = ("bot", "textboxweb", "script")

run: str = "bot"
if len(sys.argv) > 1:
	run = sys.argv[1]
	if run not in VALID_COMMANDS:
		raise ValueError(f"Invalid value passed to run script (available: {', '.join(VALID_COMMANDS)}, passed: {run})")

if run == "script":
	if len(sys.argv) < 3:
		print("Usage: python src/main.py script <script_name>")
		sys.exit(1)

	script_name = sys.argv[2]
	try:
		module = importlib.import_module(f"scripts.{script_name}")
		if hasattr(module, "run"):
			if asyncio.iscoroutinefunction(module.run):
				asyncio.run(module.run())
			else:
				module.run()
		else:
			print(f"Error: Script '{script_name}' has no run() function.")
	except ImportError:
		print(f"Error: Could not find script '{script_name}' in src/scripts/")
	sys.exit(0)

if run == "textboxweb":
	from utilities.textbox.web.run import run_server

	run_server()
	exit(0)

from interactions import Client, Intents, IntervalTrigger, Task, listen, smart_cache
from interactions.api.events import Startup

from utilities.database.main import connect_to_db
from utilities.extensions import assign_events, load_commands
from utilities.misc import set_status
from utilities.profile.main import load_profile_assets
from utilities.rolling import roll_avatar, roll_status
from utilities.stats import system_monitor_task

intents = Intents.DEFAULT | Intents.MESSAGE_CONTENT | Intents.MESSAGES | Intents.GUILD_MEMBERS | Intents.GUILDS
intents &= ~(
	Intents.GUILD_MESSAGE_REACTIONS
	| Intents.DIRECT_MESSAGE_REACTIONS
	| Intents.GUILD_INVITES
	| Intents.GUILD_MESSAGE_TYPING
	| Intents.GUILD_MODERATION
)

class TWMClient(Client):
	started_at: datetime | None
	ready_at: datetime | None
	followup_message_edited_at: datetime | None
	followup_at: datetime | None


client = TWMClient(
	intents=intents,
	send_command_tracebacks=False,
	send_not_ready_messages=True,
	sync_interactions=False,
	sync_ext=False,
	logger=createLogger("client"),
	message_cache=smart_cache.create_cache(150, 5),
	member_cache=smart_cache.create_cache(150, 5000),
	user_cache=smart_cache.create_cache(150, 5000),
)
client.started_at: datetime = datetime.now()  # type: ignore
if do_rolling := get_config("bot.rolling.avatar", typecheck=bool) or get_config("bot.rolling.status"):

	@Task.create(IntervalTrigger(get_config("bot.rolling.interval", typecheck=int)))
	async def roll():
		if get_config("bot.rolling.status", typecheck=bool) == True:
			await roll_status(client)
		if get_config("bot.rolling.avatar", typecheck=bool) == True:
			await roll_avatar(client)


assign_events(client)


@listen(Startup)
async def on_startup(event: Startup):
	asyncio.create_task(system_monitor_task())
	asyncio.create_task(set_status(client, "[ Loading... ]"))
	load_commands(client)
	await connect_to_db()
	asyncio.create_task(load_profile_assets())
	await client.wait_until_ready()
	await client._cache_interactions()
	if do_rolling:
		await roll()
		roll.start()
	logger.log(INFO, colored("The World Machine is ready! ─ 3/3\n\n", "light_magenta"))
	startupped = datetime.now()
	from extensions.events.Ready import ReadyEvent

	await ReadyEvent.followup(startupped)


logger.log(INFO, colored("Finalizing... ─ ─ ─ ─ ─ ─ ─ ─ 2/3\n\n", "light_yellow"))
client.start(get_token())