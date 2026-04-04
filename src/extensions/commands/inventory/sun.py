import random
from datetime import datetime, timedelta

from interactions import Embed, Member, OptionType, SlashContext, User, slash_option

import utilities.profile.badge_manager as bm
from utilities.database.schemas import UserData
from utilities.localization.formatting import fnum
from utilities.localization.localization import Localization, locale_format
from utilities.message_decorations import Colors, fancy_message

explosion_image = [
	"https://st.depositphotos.com/1001877/4912/i/600/depositphotos_49123283-stock-photo-light-bulb-exploding-concept-of.jpg",
	"https://st4.depositphotos.com/6588418/39209/i/600/depositphotos_392090278-stock-photo-exploding-light-bulb-dark-blue.jpg",
	"https://st.depositphotos.com/1864689/1538/i/600/depositphotos_15388723-stock-photo-light-bulb.jpg",
	"https://st2.depositphotos.com/1001877/5180/i/600/depositphotos_51808361-stock-photo-light-bulb-exploding-concept-of.jpg",
	"https://static7.depositphotos.com/1206476/749/i/600/depositphotos_7492923-stock-photo-broken-light-bulb.jpg",
]

sad_image = "https://images-ext-1.discordapp.net/external/47E2RmeY6Ro21ig0pkcd3HaYDPel0K8CWf6jumdJzr8/https/i.ibb.co/bKG17c2/image.png"

last_called: dict[int, datetime] = {}

@slash_option(
	description="Whether you want the response to be visible for others in the channel",
	name="public",
	opt_type=OptionType.BOOLEAN,
)
async def explode(self, ctx: SlashContext, public=True):
	loc = Localization(ctx, prefix="commands.inventory.sun.explode")
	uid = ctx.user.id
	explosion_amount = (await UserData(_id=uid).fetch()).times_shattered
	if uid in last_called:
		if datetime.now() < last_called[uid]:
			return await fancy_message(
				ctx,
				await locale_format(
					loc,
					loc.get("generic.command_cooldown", prefix_override="main"),
					cooldown_end=last_called[uid],
				),
				ephemeral=True,
				color=Colors.RED,
			)
	await ctx.defer(ephemeral=not public)
	last_called[uid] = datetime.now() + timedelta(seconds=20)

	random_number = random.randint(1, len(explosion_image)) - 1
	random_sadness = random.randint(1, 100)

	sad = False

	if random_sadness == 40:
		sad = True
	if not sad:
		embed = Embed(color=Colors.RED)

		dialogues: tuple[str] = await locale_format(loc, loc.get("dialogue.why", typecheck=tuple))
		dialogue = random.choice(dialogues)

		if "69" in str(explosion_amount) or "42" in str(explosion_amount):
			dialogue = await locale_format(loc, loc.get("dialogue.sixninefourtwo"))

		if len(str(explosion_amount)) > 3 and all(char == "9" for char in str(explosion_amount)):
			dialogue = await locale_format(loc, loc.get("dialogue.nineninenineninenine"))
		if not dialogue:
			dialogue = "." * random.randint(3, 9)

		embed.description = "-# " + dialogue
		embed.set_image(url=explosion_image[random_number])
		embed.set_footer(await locale_format(loc, loc.get("info"), amount=fnum(explosion_amount, ctx.locale)))
	else:
		embed = Embed(title="...")
		embed.set_image(url=sad_image)
		embed.set_footer(await locale_format(loc, loc.get("YouKilledNiko")))

	if not sad:
		await bm.increment_value(ctx, "times_shattered", 1, ctx.user)

	await ctx.send(embed=embed)


@slash_option(
	description="Person to give the sun to",
	name="who",
	opt_type=OptionType.USER,
	required=True,
)
async def sun_give(self, ctx: SlashContext, who: User):
	loc = Localization(ctx, prefix="commands.inventory.suns")
	user_data: UserData = await UserData(_id=who.id).fetch()

	if who.id == ctx.author.id:
		return await ctx.send(await locale_format(loc, loc.get("give.self"), doer=ctx.author.id))

	now = datetime.now()
	unable_until = user_data.daily_sun_timestamp

	if now < unable_until:
		return await fancy_message(
			ctx,
			await locale_format(loc, loc.get("give.errors.cooldown"), unable_until=unable_until.timestamp()),
			ephemeral=True,
			color=Colors.BAD,
		)

	if now >= unable_until:
		reset_time = now + timedelta(hours=18)
		await user_data.update(daily_sun_timestamp=reset_time)

	_ = ctx.author
	if isinstance(_, Member):
		_ = _.user

	await bm.increment_value(ctx, "suns", target=_)
	await bm.increment_value(ctx, "suns", target=who)

	await ctx.send(await locale_format(loc, loc.get("give.self"), doer=ctx.author.id))