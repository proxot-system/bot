from interactions import Embed, SlashContext, User

from utilities.database.schemas import UserData
from utilities.localization.localization import Localization, locale_format
from utilities.message_decorations import Colors
from utilities.shop.fetch_items import fetch_badge


async def earn_badge(
	ctx: SlashContext,
	badge_name: str,
	badge_data: dict,
	target: User,
	send_message: bool = True,
):
	loc = Localization(ctx)
	user_data = await UserData(_id=target.id).fetch()

	owned_badges = user_data.owned_badges
	if badge_name not in owned_badges:
		await owned_badges.append(badge_name)

	if user_data.badge_notifications and send_message:
		return await ctx.send(
			embeds=Embed(
				title=await locale_format(
					loc,
					loc.get("profile.notifications.badge.title"),
					emoji=f"<:i:{badge_data['emoji']}>",
					badge_name=badge_name,
				),
				description=await locale_format(
					loc,
					loc.get("profile.notifications.badge.description"),
					target_id=target.id,
					badge_message=await locale_format(
						loc,
						loc.get(f'profile.notifications.badge.types["{badge_data["type"]}"]'),
						amount=badge_data["requirement"],
					),
				),
				color=Colors.YELLOW,
				# footer={"text": 'You can change this notification using "/settings badge_notifications"'} # TODO: implement user /settings page # noqa: ERA001
				# await locale_format(loc, loc.get_string("profile.notifications.badge.settings_note"))# noqa: ERA001
				# await put_mini(loc, "profile.notifications.badge.settings_note", user_id=ctx.user.id)# noqa: ERA001
			),
			content=await locale_format(loc, loc.get("profile.notifications.badge.content")),
		)


async def increment_value(
	ctx: SlashContext,
	value_to_increment: str,
	amount: int = 1,
	target: User | None = None,
):
	badges = await fetch_badge()
	user = target or ctx.user

	user_data = await UserData(_id=user.id).fetch()

	await user_data.increment_key(value_to_increment, amount)

	get_value = user_data.__getattribute__(value_to_increment) + amount

	for badge, data in badges.items():
		if data["type"] == value_to_increment:
			if badge in user_data.owned_badges:
				continue

			if get_value < data["requirement"]:
				continue

			send_message = True

			if get_value > data["requirement"]:
				send_message = False
			if amount == 6:
				send_message = True
			return await earn_badge(ctx, badge, data, user, send_message)
