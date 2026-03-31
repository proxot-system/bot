import asyncio
import time
from datetime import datetime, timedelta

from aiohttp import ClientResponseError
from interactions import (
	Button,
	ButtonStyle,
	Extension,
	File,
	Member,
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
from utilities.database.schemas import UserData
from utilities.localization.formatting import fnum
from utilities.localization.localization import Localization, locale_format
from utilities.message_decorations import Colors, emojis, fancy_message
from utilities.misc import fetch
from utilities.profile.badge_manager import increment_value
from utilities.profile.main import draw_profile
from utilities.textbox.mediagen import Frame, render_textbox_frames


class ProfileCommands(Extension):
	@slash_command(description="All things to do with profiles")
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def profile(self, ctx):
		pass

	@slash_command(description="All things to do with Suns")
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def sun(self, ctx):
		pass

	@sun.subcommand(sub_cmd_description="Give someone a sun!")
	@slash_option(
		description="Person to give the sun to",
		name="who",
		opt_type=OptionType.USER,
		required=True,
	)
	async def give(self, ctx: SlashContext, who: User):
		user_data: UserData = await UserData(_id=who.id).fetch()

		if who.bot:
			return await fancy_message(ctx, "[ Bot's can't receive suns! ]", color=Colors.BAD, ephemeral=True)

		if who.id == ctx.author.id:
			return await fancy_message(ctx, "[ Nuh uh! ]", color=Colors.BAD, ephemeral=True)

		now = datetime.now()

		last_reset_time = user_data.daily_sun_timestamp

		if now < last_reset_time:
			time_unix = last_reset_time.timestamp()
			return await fancy_message(
				ctx,
				f"[ You've already given a sun to someone! You can give one again <t:{int(time_unix)}:R>. ]",
				ephemeral=True,
				color=Colors.BAD,
			)

		# reset the limit if it is a new day
		if now >= last_reset_time:
			reset_time = now + timedelta(days=1)
			await user_data.update(daily_sun_timestamp=reset_time)
		_ = ctx.author
		if isinstance(_, Member):
			_ = _.user
		await increment_value(ctx, "suns", target=_)
		await increment_value(ctx, "suns", target=who)

		await ctx.send(f"[ {ctx.author.mention} gave {who.mention} a sun! {emojis['icons']['sun']} ]")

	@profile.subcommand(sub_cmd_description="View a profile")
	@slash_option(
		description="Person you want to see the profile of",
		name="user",
		opt_type=OptionType.USER,
	)
	async def view(self, ctx: SlashContext, user: User | None = None):
		url = "https://theworldmachine.xyz/profile"

		loc = Localization(ctx)
		if user is None:
			user = ctx.user
		if user.bot and ctx.client.user != user:
			return await ctx.send(await locale_format(loc, loc.get("profile.view.bots")), ephemeral=True)

		await fancy_message(ctx, await locale_format(loc, loc.get("profile.view.loading"), target_id=user.id))

		start_time = time.perf_counter()
		image = await draw_profile(
			user,
			filename=await locale_format(loc, loc.get("profile.view.image.name"), target_id=user.id),
			loc=loc,
		)
		runtime = (time.perf_counter() - start_time) * 1000
		components = []
		if user == ctx.user:
			components.append(
				Button(
					style=ButtonStyle.URL,
					url=url,
					label=await locale_format(loc, loc.get("profile.view.button")),
				)
			)
		content = await locale_format(loc, loc.get("profile.view.message"), target_id=user.id)
		await ctx.edit(
			content=f"-# Took {fnum(runtime, locale=loc.locale)}ms. {content}" if debugging() else f"-# {content}",
			files=image,
			components=components,
			allowed_mentions={"users": []},
			embeds=[],
		)

	@profile.subcommand(sub_cmd_description="Edit your profile")
	async def edit(self, ctx: SlashContext):
		loc = Localization(ctx)
		components = [
			Button(
				style=ButtonStyle.URL,
				label=await locale_format(loc, loc.get("generic.buttons.open_site")),
				url=get_config("bot.links.website-root") + "/profile",
			)
		]
		asyncio.create_task(
			fancy_message(
				ctx,
				message=await locale_format(loc, loc.get("profile.edit.text")),
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
					label=await locale_format(loc, loc.get('about.buttons["community server"]')),
					url=get_config("bot.links.discord-invite"),
				)
			)
			buffer = await render_textbox_frames(
				[Frame(str(await locale_format(loc, loc.get("profile.edit.down"))))], loops=1, loc=loc
			)
			filename = (
				await locale_format(
					loc,
					loc.get("commands.textbox.create.alt.single_frame.filename"),
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
	]  # TODO: what is this
