import asyncio
import time
from datetime import datetime

from aiohttp import ClientResponseError
from interactions import (
	Button,
	ButtonStyle,
	Extension,
	File,
	OptionType,
	SlashCommandChoice,
	SlashContext,
	User,
	contexts,
	integration_types,
	slash_command,
	slash_option,
)

from utilities.config import debugging, get_config
from utilities.localization.formatting import fnum
from utilities.localization.localization import Localization, locale_format
from utilities.message_decorations import fancy_message
from utilities.misc import fetch
from utilities.profile.main import draw_profile
from utilities.textbox.mediagen import Frame, render_textbox_frames


class ProfileCommands(Extension):
	@slash_command(description="All things to do with profiles")
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def profile(self, ctx):
		pass

	@profile.subcommand(sub_cmd_description="View a profile")
	@slash_option(
		description="Person you want to see the profile of",
		name="user",
		opt_type=OptionType.USER,
	)
	async def view(self, ctx: SlashContext, user: User | None = None):
		url = "https://theworldmachine.xyz/profile"

		loc = Localization(ctx, prefix="commands.profile")
		if user is None:
			user = ctx.user
		if user.bot and not (
			user.id == int(get_config("bot.main.nikobotId", raise_on_not_found=False) or 0) or user.id == ctx.user.id
		):
			return await ctx.send(await locale_format(loc, loc.get("view.bots")), ephemeral=True)

		loading = asyncio.create_task(
			fancy_message(ctx, await locale_format(loc, loc.get("view.loading"), target_id=user.id))
		)

		start_time = time.perf_counter()
		image = await draw_profile(
			user,
			filename=await locale_format(loc, loc.get("view.image.name"), target_id=user.id),
			loc=loc,
		)
		runtime = (time.perf_counter() - start_time) * 1000
		components = []
		if user == ctx.user:
			components.append(
				Button(
					style=ButtonStyle.URL,
					url=url,
					label=await locale_format(loc, loc.get("view.button")),
				)
			)
		content = await locale_format(loc, loc.get("view.message"), target_id=user.id)
		await loading
		await ctx.edit(
			content=f"-# Took {fnum(runtime, locale=loc.locale)}ms. {content}" if debugging() else f"-# {content}",
			files=image,
			components=components,
			allowed_mentions={"users": []},
			embeds=[],
		)

	@profile.subcommand(sub_cmd_description="Edit your profile")
	async def edit(self, ctx: SlashContext):
		loc = Localization(ctx, prefix="commands.profile")
		components = [
			Button(
				style=ButtonStyle.URL,
				label=await locale_format(loc, loc.get("generic.buttons.open_site", prefix_override="main")),
				url=get_config("bot.links.websiteRoot") + "/profile",
			)
		]
		asyncio.create_task(
			fancy_message(
				ctx,
				message=await locale_format(loc, loc.get("edit.text")),
				ephemeral=True,
				components=components,
			)
		)
		try:
			await fetch("https://theworldmachine.xyz/profile")
		except ClientResponseError:
			components.append(
				Button(
					style=ButtonStyle.URL,
					label=await locale_format(loc, loc.get('buttons["community server"]', prefix_override="commands.info.about")),
					url=get_config("bot.links.discordInvite"),
				)
			)
			buffer = await render_textbox_frames(
				[Frame(str(await locale_format(loc, loc.get("edit.down"))))], loops=1, loc=loc
			)
			filename = (
				await locale_format(
					loc,
					loc.get("alt.single_frame.filename", prefix_override="commands.textbox.create"),
					timestamp=str(round(datetime.now().timestamp())),
				)
				+ ".webp"
			)

			await ctx.edit(
				files=File(file=buffer, file_name=filename),
				embeds=[],
				components=components,
			)
		except Exception:
			pass

	choices = [
		SlashCommandChoice(name="Sun Amount", value="suns"),
		SlashCommandChoice(name="Wool Amount", value="wool"),
		SlashCommandChoice(name="Times Shattered", value="times_shattered"),
		SlashCommandChoice(name="Times Asked", value="times_asked"),
		SlashCommandChoice(name="Times Messaged", value="times_messaged"),
		SlashCommandChoice(name="Times Transmitted", value="times_transmitted"),
	]
