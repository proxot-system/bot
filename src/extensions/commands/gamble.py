import asyncio
import random
from dataclasses import dataclass
from typing import Literal

from interactions import (
	Color,
	Embed,
	Extension,
	OptionType,
	SlashContext,
	contexts,
	integration_types,
	slash_command,
	slash_option,
)

from utilities.database.schemas import UserData
from utilities.emojis import emojis
from utilities.localization.localization import Localization, locale_format
from utilities.message_decorations import Colors, fancy_message


@dataclass
class Slot:
	emoji: str
	value: float

	def __init__(self, emoji: str, value: float):
		rounded = round(value * 100)
		self.emoji = emoji.replace(":i:", f":{rounded if rounded > 0 else 'minus_' + str(0 - rounded)}pts:")
		self.value = value

	def __eq__(self, other):
		if isinstance(other, Slot):
			return self.emoji == other.emoji and self.value == other.value
		return False

	def __hash__(self):
		return hash((self.emoji, self.value))

	def __lt__(self, other):
		return self.value < other.value


et = emojis["treasures"]
slots = [
	Slot(et["bottle"], 0.1),
	Slot(et["journal"], 0.15),
	Slot(et["amber"], 0.2),
	Slot(et["shirt"], 0.5),
	Slot(et["bottle"], 0.1),
	Slot(et["journal"], 0.15),
	Slot(et["amber"], 0.2),
	Slot(et["shirt"], 0.5),
	Slot(et["card"], 0.8),
	Slot(et["die"], 1.0),
	Slot(et["sun"], 1.12),
	Slot(et["clover"], 1.5),
	Slot(emojis["icons"]["penguin"], -0.2),
	Slot(emojis["icons"]["penguin"], -0.2),
	Slot(emojis["icons"]["penguin"], -0.2),
]


class GambleCommands(Extension):
	@slash_command(description="Commands related to gambling")
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def gamble(self, ctx: SlashContext):
		pass

	@gamble.subcommand(sub_cmd_description="Waste your wool away with slots. Totally not a scheme by Magpie")
	@slash_option(
		description="How much wool would you like to bet?",
		name="bet",
		required=True,
		opt_type=OptionType.INTEGER,
		min_value=100,
	)
	async def wool(self, ctx: SlashContext, bet: int):
		loc = Localization(ctx, prefix="commands.gamble")
		await fancy_message(ctx, await locale_format(loc, loc.get("generic.loading.generic", prefix_override="main")))
		user_data: UserData = await UserData(_id=ctx.author.id).fetch()

		if user_data.wool < bet:
			return await fancy_message(
				ctx,
				await locale_format(loc, loc.get("wool.errors.not_enough_wool")),
				ephemeral=True,
				color=Colors.BAD,
			)

		# TAKE the wool
		await user_data.manage_wool(-bet)

		rows = [random.sample(slots, len(slots)) for _ in range(3)]

		def img_all(*args):
			return [slot.emoji for slot in args]

		def generate_column(rows: list[Slot], i: int):
			slot_a = 0
			slot_b = 0
			slot_c = 0

			if i == len(rows) - 1:
				slot_c = rows[0]
			else:
				slot_c = rows[i + 1]

			if i == 0:
				slot_a = rows[-1]
			else:
				slot_a = rows[i - 1]

			slot_b = rows[i]

			return img_all(slot_a, slot_b, slot_c)

		slot_images: list[list] = []
		slot_values = [0.0, 0.0, 0.0]

		async def generate_embed(
			index: int,
			column: int,
			columns: list[list],
			result: tuple[
				Literal["jackpot", "lost_some", "won_some", "pain", "lost_all"],
				int,
				int,
				Color,
			]
			| None = None,
		):
			nonlocal slot_values

			def grab_slot(i: int):
				column = generate_column(rows[i], index)

				try:
					del columns[i]
				except:
					pass

				columns.insert(i, list(column))

				return columns

			if column == -1:
				grab_slot(0)
				grab_slot(1)
				columns = grab_slot(2)
			else:
				columns = grab_slot(column)

			ticker = ""

			for row in range(3):
				for col in range(3):
					# slot_images are columns
					c = columns[col]

					s = f"{c[row]}"

					if col == 2:
						if row == 1:
							if result:
								ticker += f"{s} ⇦ {result[1]}\n"
							else:
								ticker += f"{s} ⇦\n"
						else:
							ticker += f"{s}\n"
					elif col == 0:
						ticker += f"## {s} ┋ "
					else:
						ticker += f"{s} ┋ "
			return Embed(
				description=f"## {await locale_format(loc, loc.get('wool.slots.title'))}\n\n"
				+ await locale_format(
					loc,
					loc.get(f"wool.slots.description_{'running' if not result else 'result'}"),
					bettor_id=ctx.author.id,
					bet_amount=bet,
					result=result[0] if result else None,
					ticker=ticker,
					win_amount=result[2] if result else None,
				),
				color=Colors.DEFAULT,
			)

		await ctx.edit(embed=await generate_embed(0, -1, slot_images))

		sleep_first_rotata_s = 3
		for column in range(0, 3):
			max_rolls = random.randint(8, 9) if column == 2 else 8
			for i in range(max_rolls):
				await asyncio.sleep(sleep_first_rotata_s * ((i + 1) / max_rolls) ** 1.5)

				result_embed = await generate_embed(i, column, slot_images)
				await ctx.edit(embed=result_embed)
				slot_values[column] = rows[column][i].value

		if result_embed.description is not None:
			result_embed.description = result_embed.description.replace("⇦", "⇦ " + str(round(sum(slot_values) * 100)))

		additional_scoring = 1
		jackpot = False
		if all(x == slot_values[0] for x in slot_values):
			jackpot = True
			additional_scoring = 100
		if user_data.wool < 25:
			additional_scoring += 14
		win_amount = int(sum(slot_values) * additional_scoring * (bet / 2))

		if win_amount < 0:
			win_amount = 0

		# EVIL line of code that either takes or gives the wool
		await user_data.manage_wool(win_amount)

		if win_amount > 0:
			if additional_scoring > 1:
				result_color = Colors.PURE_YELLOW
				result = "jackpot"
			else:
				if win_amount < bet:
					result_color = Colors.PURE_ORANGE
					result = "lost_some"
				else:
					result_color = Colors.PURE_GREEN
					result = "won_some"
		else:
			result_color = Colors.PURE_RED
			result = "pain" if jackpot else "lost_all"

		await ctx.edit(
			embed=await generate_embed(
				i,
				column,
				slot_images,
				(result, round(sum(slot_values) * 100), win_amount, result_color),
			)
		)

	@gamble.subcommand(sub_cmd_description="Read up on how the gamble command works")
	async def help(self, ctx: SlashContext):
		loc = Localization(ctx, prefix="commands.gamble")

		tasks = []
		for slot in sorted(set(slots)):
			value = int(abs(slot.value) * 100)
			tasks.append(
				loc.format(
					loc.get("wool.slots.guide.value_entry"),
					icon=slot.emoji,
					value=value,
					value_sign="negative" if slot.value < 0 else "positive",
				)
			)

		point_rows = await asyncio.gather(*tasks)

		await fancy_message(
			ctx,
			f"## {await locale_format(loc, loc.get('wool.slots.title'))}\n"
			+ await locale_format(loc, loc.get("wool.slots.guide.description"), slot_values="\n".join(point_rows)),
		)