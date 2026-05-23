import os
import random

from interactions import Client, File
from interactions.client.errors import TooManyChanges
from termcolor import colored

from utilities.config import debugging, get_config, on_prod
from utilities.misc import set_avatar, set_status

available_avatars = os.listdir("src/data/images/profile_pictures")


async def roll_avatar(client: Client, log=True, print=print) -> None:
	if log:
		if debugging():
			print("Rolling avatar...")
		else:
			print("Rolling avatar ... \033[s", flush=True)
	random_avatar = random.choice(available_avatars)
	if on_prod:
		try:
			await set_avatar(client, File(f"src/data/images/profile_pictures/{random_avatar}"))
		except TooManyChanges:
			e = " It's recommended you disable avatar rolling, or set the interval to a slower pace."
			if not debugging():
				print(f"\033[u" + colored("failed." + e, "red"), flush=True)
				return print("\033[999B", end="", flush=True)
			else:
				return print("..." + colored("failed." + e, "red"))
		if log:
			if not debugging():
				print(f"\033[uused {random_avatar}", flush=True)
				print("\033[999B", end="", flush=True)
			else:
				print(f"...used {random_avatar}")
	else:
		avatar = File("src/data/images/unstable.png")
		try:
			await set_avatar(client, avatar)
			if not debugging():
				print(f"\033[uused unstable", flush=True)
				print("\033[999B", end="", flush=True)
			else:
				print(f"...used unstable")
		except:
			if not debugging():
				print(f"\033[ufailure", flush=True)
				print("\033[999B", end="", flush=True)
			else:
				print(f"...failure")


statuses = get_config("bot.rolling.statuses", typecheck=list, ignore_None=True)


async def roll_status(client: Client, log=True, print=print) -> None:
	status = (
		statuses
		if isinstance(statuses, str)
		else random.choice(statuses if statuses is not None else [None])
		if isinstance(statuses, list)
		else None
	)
	if log:
		if not debugging():
			print(f"Rolled status: {await set_status(client, status)}")
		else:
			print("Rolling status...")
			status = await set_status(client, status)
			print(f"...attempted to set to: {status}")
