import asyncio
import random
import re
import time
import traceback as tb
from traceback import print_exc

import aiohttp
from aioconsole import aexec
from interactions import (
	Embed,
	Extension,
	OptionType,
	SlashContext,
	contexts,
	integration_types,
	slash_command,
	slash_option,
)

from utilities.config import get_config
from utilities.dev_commands import redir_prints
from utilities.localization.formatting import fnum
from utilities.localization.localization import Localization, lformat
from utilities.message_decorations import Colors, fancy_message
from utilities.misc import fetch
from utilities.textbox.facepics import get_facepic

ansi_escape_pattern = re.compile(r"\033\[[0-9;]*[A-Za-z]")


class MiscellaneousCommands(Extension):
	@slash_command(description="A random wikipedia article")
	@slash_option(
		description="Whether you want the response to be visible for others in the channel",
		name="public",
		opt_type=OptionType.BOOLEAN,
	)
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def random_wikipedia(self, ctx: SlashContext, public: bool = False):
		loc = Localization(ctx)
		await fancy_message(ctx, message=await lformat(loc, loc.l("generic.loading.generic")), ephemeral=not public)
		try:
			response = await fetch("https://en.wikipedia.org/api/rest_v1/page/random/summary", output="json")
		except:
			print_exc()
			return await fancy_message(
				ctx, edit=True, message=await lformat(loc, loc.l("generic.loading.failed")), ephemeral=not public
			)

		await fancy_message(
			ctx,
			await lformat(
				loc,
				loc.l("commands.misc.commands.random_wikipedia.wikipedia"),
				link=response["content_urls"]["desktop"]["page"],
				title=response["title"],
			),
			edit=True,
		)

	@slash_command(description="bogus")
	@slash_option(
		description="Whether you want the response to be visible for others in the channel",
		name="public",
		opt_type=OptionType.BOOLEAN,
	)
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def amogus(self, ctx: SlashContext, public: bool = False):
		await ctx.send(
			"https://media.discordapp.net/attachments/868336598067056690/958829667513667584/1c708022-7898-4121-9968-0f0d24b8f986-1.gif",
			ephemeral=not public,
		)

	@slash_command(description="rewrites the bot in python")
	@slash_option(
		description="Whether you want the response to be visible for others in the channel",
		name="public",
		opt_type=OptionType.BOOLEAN,
	)
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def python(self, ctx: SlashContext, public: bool = False):
		return await ctx.send(
			"https://cdn.discordapp.com/attachments/1164430884733198416/1412555496296153262/python.gif?ex=68b8b852&is=68b766d2&hm=d13a559d48e65cabfeb1ab642146a8f34f068c336426ae140233c77ea17c973e&",
			ephemeral=not public,
		)

	@slash_command(description="Show a picture of a kitty or a cat or a Catto")
	@slash_option(
		description="Whether you want the response to be visible for others in the channel",
		name="public",
		opt_type=OptionType.BOOLEAN,
	)
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def cat(self, ctx: SlashContext, public: bool = False):
		loc = Localization(ctx, prefix="commands.misc.commands.cat")
		embed = Embed(title=await lformat(loc, loc.l("miaou.title")), color=Colors.DEFAULT)

		if random.randint(0, 100) == 30 + 6 + 14:
			embed.description = await lformat(loc, loc.l("miaou.finding.noik"))
			embed.set_image(
				"https://cdn.discordapp.com/attachments/1028022857877422120/1075445796113219694/ezgif.com-gif-maker_1.gif"
			)
			embed.set_footer(await lformat(loc, loc.l("miaou.finding.footer", return_None_on_not_found=True) or ""))
			return await ctx.send(embed=embed)

		async with aiohttp.ClientSession() as session:
			async with session.get("https://api.thecatapi.com/v1/images/search") as response:
				data = await response.json()

		image = data[0]["url"]

		embed.description = await lformat(loc, loc.l("miaou.finding.cat"))
		embed.set_image(image)
		return await ctx.send(embed=embed, ephemeral=not public)

	@slash_command(description="eval code in slash context (bot developer only)")
	@slash_option(description="wa to eval", name="code", opt_type=OptionType.STRING, required=True)
	@slash_option(
		description="try to send without ephemeral",
		name="public",
		opt_type=OptionType.BOOLEAN,
	)
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def eval(self, ctx: SlashContext, code: str, public: bool = False):
		loc = Localization(ctx)
		await fancy_message(
			ctx,
			await lformat(loc, loc.l("generic.loading.checking_developer_status")),
			ephemeral=True,
		)

		if str(ctx.author.id) not in get_config("dev.whitelist", typecheck=list):
			await asyncio.sleep(3)
			return await fancy_message(
				ctx,
				await lformat(loc, loc.l("generic.errors.not_a_developer")),
				facepic=await get_facepic("OneShot (fan)/Nikonlanger/Jii"),
				edit=True,
			)

		asyncio.create_task(
			fancy_message(ctx, await lformat(loc, loc.l("generic.loading.evaluating")), ephemeral=not public)
		)

		method = "eval"
		if "\n" in code or "import " in code or "await " in code or "return " in code:
			method = "aexec" if "await" in code else "exec"

		result = None
		state = {"asnyc_warn": False, "strip_ansi_sequences": True, "raisure": False}
		start_time = time.perf_counter()

		try:
			if method == "exec":
				result = redir_prints(exec, code, locals(), globals())
			elif method == "aexec":
				result = await redir_prints(aexec, code, locals())
			else:
				if not code.strip():
					raise ValueError("no code provided")
				result = eval(code, globals(), locals())
		except Exception:
			state["raisure"] = True
			raw_err = tb.format_exc(chain=True)
			result = raw_err.replace('  File "<aexec>", ', " - at ").replace('  File "<string>", ', " - at ")

			if " in redir_prints" in result:
				result = result.split("method(code, globals, locals)")[1]
			elif "new_local = await coro" in result:
				state["asnyc_warn"] = True
				result = result.split("^^^^^^^^^^")[1]

		runtime = (time.perf_counter() - start_time) * 1000

		def build_embed(output_val, note=""):
			res_str = str(output_val)
			if state["strip_ansi_sequences"]:
				res_str = ansi_escape_pattern.sub("", res_str)

			desc = f"-# Runtime: {fnum(runtime)} ms{note}"
			if state["asnyc_warn"]:
				desc += "\n-# Line numbers offset by +1"

			if not res_str.strip() and method != "eval":
				desc += "\n-# Nothing was printed"
			else:
				if len(res_str) > 3900:
					res_str = res_str[:3850] + "\n... (truncated)"
				desc += f"\n```py\n{res_str.replace('```', '` ``')}```"

			return Embed(
				color=Colors.BAD if state["raisure"] else Colors.DEFAULT,
				description=desc,
			)

		try:
			return await ctx.edit(embeds=build_embed(result))
		except Exception as e:
			return await ctx.edit(embeds=build_embed("Output too complex to display", note=f"\n⚠️ Send Error: {e}"))