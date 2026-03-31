import asyncio
from typing import Literal

from utilities.database.schemas import UserData
from utilities.localization.localization import Localization, locale_format


async def put_mini(
	loc: Localization,
	message: str,
	show_up_amount: int = -1,
	user_id: str | int | None = None,
	type: Literal["note", "tip", "warn", "err"] = "note",
	pre: str = "",
	markdown: bool = True,
) -> str:
	database_key = loc.prefix + "." + message
	if user_id:
		user_data: UserData = await UserData(str(user_id)).fetch()
		reacher = user_data.minis_shown.get(message, 0)
		if show_up_amount != -1 and show_up_amount <= reacher:
			return ""
		asyncio.create_task(user_data.minis_shown.increment_key(database_key))
	name: str = await locale_format(loc, loc.get(f"generic.minis.{type}", prefix_override="main"))
	msg: str = await locale_format(loc, loc.get(message))
	return f"{pre}{'-# ' if markdown else ''}{name} {msg}"
