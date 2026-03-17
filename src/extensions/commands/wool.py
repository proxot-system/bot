import asyncio
import random
from datetime import datetime, timedelta

from interactions import (
	Button,
	ButtonStyle,
	Embed,
	EmbedAttachment,
	Extension,
	OptionType,
	SlashContext,
	User,
	contexts,
	integration_types,
	slash_command,
	slash_option,
)

from utilities.database.schemas import UserData
from utilities.emojis import emojis, make_emoji_cdn_url
from utilities.localization.formatting import fnum
from utilities.localization.localization import Localization, locale_format
from utilities.localization.minis import put_mini
from utilities.message_decorations import Colors, fancy_message
from utilities.textbox.facepics import get_facepic

# fmt: off
wool_finds = {
  10: [ "devoted", "positive_major"   ],
  30: [  "yippie", 'positive_normal'  ],
  60: [    "ogie", 'positive_minimum' ],
  70: [ "misdeed", 'negative_minimum' ],
  95: [ "unhappy", "negative_normal"  ],
 100: [ "despise", 'negative_major'   ]
}
wool_values = {
   'positive_major': [  5_000, 20_000  ],
  'positive_normal': [  3_000, 5_000   ],
 'positive_minimum': [    500, 3_000   ],
 'negative_minimum': [    -10, -1_000  ],
  'negative_normal': [ -1_000, -5_000  ],
   'negative_major': [ -5_000, -30_000 ]
}
# fmt: on
wool_give_blacklist = ["545986448231497728", "611543231192236051"]


class WoolCommands(Extension):
	@slash_command(description="All things to do with wool")
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def wool(self, ctx: SlashContext):
		pass

	@wool.subcommand(sub_cmd_description="View the balance")
	@slash_option(
		description="The person you want to view balance of instead (defaults to yours)",
		name="of",
		opt_type=OptionType.USER,
	)
	@slash_option(
		description="Whether you want the response to be visible for others in the channel",
		name="public",
		opt_type=OptionType.BOOLEAN,
	)
	async def balance(self, ctx: SlashContext, of: User | None = None, public: bool = False):
		await ctx.defer(ephemeral=not public)
		loc = Localization(ctx)
		if of is None:
			of = ctx.user

		user_data: UserData = await UserData(_id=of.id).fetch()
		wool: int = user_data.wool
		who_path = "other"
		if not public and of == ctx.user:
			who_path = "you"
		if of == ctx.client.user:
			who_path = "twm"
		elif of.bot:
			who_path = "bot"
		return await fancy_message(
			ctx,
			await locale_format(
				loc,
				loc.get_string(f"wool.balance.{who_path}.{'none' if wool == 0 else 'some'}"),
				account_holder_id=of.id,
				balance=fnum(wool, locale=ctx.locale),
			),
			edit=True,
		)

	@wool.subcommand(sub_cmd_description="Give away some of your wool")
	@slash_option(
		description="Who would you like to give?",
		name="to",
		required=True,
		opt_type=OptionType.USER,
	)
	@slash_option(
		description="How much wool would you like to give them?",
		name="amount",
		required=True,
		opt_type=OptionType.INTEGER,
		min_value=-1,
	)
	async def give(self, ctx: SlashContext, to: User, amount: int):
		loc = Localization(ctx)
		ephemeral_override = None
		if ctx.guild:
			bot_member = ctx.guild.get_member(ctx.client.user.id)
			if bot_member:
				ephemeral_override = False
		if str(ctx.author.id) in wool_give_blacklist:
			return await ctx.send(
				"https://cdn.discordapp.com/attachments/1336864890706595852/1433821383435223233/TWM_textbox_1761920034.png",
				ephemeral=True,
			)

		if to.id == ctx.author.id:
			return await fancy_message(
				ctx,
				await locale_format(loc, loc.get_string("wool.transfer.errors.self_transfer")),
				ephemeral=True,
				color=Colors.BAD,
			)

		if to.bot and not (amount <= 0):
			buttons = [
				Button(
					style=ButtonStyle.RED,
					label=await locale_format(loc, loc.get_string("generic.buttons.yes")),
					custom_id="yes",
				),
				Button(
					style=ButtonStyle.GRAY,
					label=await locale_format(loc, loc.get_string("generic.buttons.cancel")),
					custom_id="cancel",
				),
			]

			confirmation_m = await fancy_message(
				ctx,
				message=await locale_format(loc, loc.get_string("wool.transfer.to.bot.confirmation"))
				+ await put_mini(
					loc,
					"wool.transfer.to.bot.notefirmation",
					user_id=ctx.user.id,
					show_up_amount=10,
					pre="\n\n",
				),
				color=Colors.WARN,
				components=buttons,
				facepic=await get_facepic("OneShot/The World Machine/Looking Left"),
				ephemeral=True,
			)
			try:
				response = await ctx.client.wait_for_component(messages=confirmation_m, timeout=60.0 * 1000)
				await ctx.delete(confirmation_m)
				if response.ctx.custom_id == "cancel":
					return
			except asyncio.TimeoutError:
				await confirmation_m.edit(
					content=await locale_format(loc, loc.get_string("generic.responses.timeout.yn")), components=[]
				)
				await ctx.delete()
				await asyncio.sleep(15)
				return await confirmation_m.delete()

		loading = asyncio.create_task(
			fancy_message(
				ctx,
				await locale_format(loc, loc.get_string("generic.loading.hint")),
				ephemeral=ephemeral_override if ephemeral_override is not None else False,
			)
		)
		from_user: UserData = await UserData(_id=ctx.author.id).fetch()
		to_user: UserData = await UserData(_id=to.id).fetch()

		await loading
		if from_user.wool < amount:
			return await fancy_message(
				ctx,
				await locale_format(
					loc,
					loc.get_string("wool.transfer.errors.not_enough"),
					balance=from_user.wool,
					sender_id=from_user._id,
					receiver_id=to_user._id,
				)
				+ await put_mini(loc, "wool.transfer.errors.note_nuf", pre="\n\n"),
				edit=True,
				ephemeral=True,
				color=Colors.BAD,
			)

		if not amount == 0:
			await from_user.manage_wool(-amount)
			await to_user.manage_wool(amount)

		if amount < 0:
			return await fancy_message(
				ctx,
				await locale_format(
					loc,
					loc.get_string("wool.transfer.steal"),
					sender_id=from_user._id,
					receiver_id=to_user._id,
				),
				edit=True,
			)
		await fancy_message(
			ctx,
			await locale_format(
				loc,
				loc.get_string(f"wool.transfer.to.{'bot' if to.bot else 'user'}.{'none' if amount == 0 else 'some'}"),
				sender_id=from_user._id,
				receiver_id=to_user._id,
				amount=amount,
			),
			edit=True,
		)

	@slash_command(description="Pray to The World Machine")
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def pray(self, ctx: SlashContext):
		loc = Localization(ctx)

		user_data: UserData = await UserData(_id=ctx.author.id).fetch()
		unable_until = user_data.daily_wool_timestamp

		now = datetime.now()

		if unable_until and now < unable_until:
			return await fancy_message(
				ctx,
				await locale_format(
					loc,
					loc.get_string("wool.pray.errors.timeout"),
					unable_until=unable_until,
				),
				ephemeral=True,
				color=Colors.BAD,
			)

		# reset the limit if it is a new day
		if now >= unable_until:
			reset_time = datetime.combine(now.date(), now.time()) + timedelta(days=1)
			await user_data.update(daily_wool_timestamp=reset_time)
		rolled = random.randint(0, 100)

		finding = wool_finds[min(wool_finds.keys(), key=lambda k: abs(k - rolled))]
		amount = wool_values[finding[1]]
		amount = int(random.uniform(amount[0], amount[1]))

		await user_data.manage_wool(amount)

		await ctx.send(
			embed=Embed(
				thumbnail=EmbedAttachment(make_emoji_cdn_url(emojis["treasures"]["die"])),
				title=await locale_format(loc, loc.get_string("wool.pray.title")),
				description=f"{await locale_format(loc, loc.get_string(f'wool.pray.finds.{finding[0]}'))}\n-# "
				+ await locale_format(
					loc,
					loc.get_string(f"wool.pray.Change.{'gain' if amount > 0 else 'loss'}"),
					amount=abs(amount),
				),
				color=Colors.GREEN if amount > 0 else Colors.BAD,
			)
		)
