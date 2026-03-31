import random

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

from utilities.localization.localization import Localization, locale_format
from utilities.message_decorations import Colors, fancy_message
from utilities.textbox.facepics import get_facepic


class ShippingCommands(Extension):
	@slash_command(description="Ship two people together")
	@slash_option(
		name="who",
		description="First person (singular, can be a @user)",
		opt_type=OptionType.STRING,
		required=True,
	)
	@slash_option(
		argument_name="whomst",
		name="with",
		description="Second person (singular, can be a @user)",
		opt_type=OptionType.STRING,
		required=True,
	)
	@slash_option(
		description="Whether you want the response to be visible for others in the channel (default: True)",
		name="public",
		opt_type=OptionType.BOOLEAN,
	)
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def ship(self, ctx: SlashContext, who: str, whomst: str, public: bool = True):
		loc = Localization(ctx, prefix="commands.ship")
		if "<" in who and ">" in who:
			parsed_id = who.strip("<>")
			if parsed_id.count("@") > 1:
				return await fancy_message(
					ctx,
					await locale_format(loc, loc.get("errors.idk")),
					color=Colors.BAD,
					ephemeral=True,
				)
			parsed_id = parsed_id.strip("@")
			if not parsed_id.isdigit():
				return await fancy_message(
					ctx,
					await locale_format(loc, loc.get("errors.failed_mention")),
					color=Colors.BAD,
					ephemeral=True,
				)
			user = await ctx.client.fetch_user(int(parsed_id))
			if not user:
				return await fancy_message(
					ctx,
					await locale_format(loc, loc.get("errors.cant_find_one")),
					color=Colors.BAD,
					ephemeral=True,
				)
			who = user.display_name
		if "<" in whomst and ">" in whomst:
			parsed_id = whomst.strip("<>")
			if parsed_id.count("@") > 1:
				return await fancy_message(
					ctx,
					await locale_format(loc, loc.get("errors.idk")),
					color=Colors.BAD,
					ephemeral=True,
					facepic=await get_facepic("OneShot/The World Machine/Upset left"),
				)
			parsed_id = parsed_id.strip("@")
			if not parsed_id.isdigit():
				return await fancy_message(
					ctx,
					await locale_format(loc, loc.get("errors.failed_mention")),
					color=Colors.BAD,
					ephemeral=True,
					facepic=await get_facepic("OneShot/The World Machine/Looking Left"),
				)
			user = await ctx.client.fetch_user(int(parsed_id))
			if not user:
				return await fancy_message(
					ctx,
					await locale_format(loc, loc.get("errors.cant_find_two")),
					color=Colors.BAD,
					ephemeral=True,
					facepic=await get_facepic("OneShot/The World Machine/Upset left"),
				)
			whomst = user.display_name
		if who == ctx.author.display_name and who == whomst:
			return await fancy_message(
				ctx,
				await locale_format(loc, loc.get("errors.hugs_you")),
				color=Colors.BAD,
				ephemeral=True,
				facepic=await get_facepic("OneShot/The World Machine/Looking Left"),
			)

		seed = len(who) + len(whomst)
		random.seed(seed)
		love_percentage = random.randint(0, 100)

		name_a_part = who[0 : len(who) // 2]  # Get the first half of the first name.
		name_b_part = whomst[-len(whomst) // 2 :]  # Get the last half of the second name.

		name = name_a_part + name_b_part  # Combine the names together.

		emoji = "💖"
		footer = ""
		color = Colors.PASTEL_RED
		if love_percentage == 100:
			emoji = "💛"
			footer = await locale_format(loc, loc.get("compatibility.footer.perfect"))
			color = Colors.PURE_YELLOW
		if love_percentage < 100:
			emoji = "💖"
			footer = await locale_format(loc, loc.get("compatibility.footer.love"))
			color = Colors.PINK
		if love_percentage < 70:
			emoji = "❤"
			footer = await locale_format(loc, loc.get("compatibility.footer.interest"))
		if love_percentage <= 50:
			emoji = "❓"
			footer = await locale_format(loc, loc.get("compatibility.footer.potential"))
		if love_percentage < 30:
			emoji = "❌"
			footer = await locale_format(loc, loc.get("compatibility.footer.disinterest"))
		if love_percentage < 10:
			emoji = "💔"
			footer = await locale_format(loc, loc.get("compatibility.footer.nope"))
			color = Colors.LIGHTER_BLACK

		hearts_line = list("🤍🤍🤍🤍🤍🤍🤍🤍🤍🤍")

		calc_length = round((love_percentage / 100) * len(hearts_line))

		i = 0
		for _ in hearts_line:
			if i < calc_length:
				hearts_line[i] = emoji
			i += 1

		embed = Embed(
			title=name,
			description=f"{await locale_format(loc, loc.get('compatibility.description'), who=who, whomst=whomst, emoji=emoji, percentage=love_percentage)}\n{''.join(hearts_line)}\n-# {footer}",
			color=color,
		)

		await ctx.send(embeds=embed, ephemeral=not public)
