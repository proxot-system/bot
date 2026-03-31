import asyncio
import math
import random
import re
from asyncio import TimeoutError
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Union

from interactions import (
	ActionRow,
	BaseComponent,
	Button,
	ButtonStyle,
	ComponentContext,
	Embed,
	Extension,
	InteractionContext,
	Modal,
	ModalContext,
	OptionType,
	ShortText,
	SlashContext,
	StringSelectMenu,
	StringSelectOption,
	User,
	component_callback,
	contexts,
	integration_types,
	modal_callback,
	slash_command,
	slash_option,
)
from interactions.api.events import Component

from extensions.commands.shop import pancake_id_to_emoji_index_please_rename_them_in_db
from utilities.database.schemas import Nikogotchi, StatUpdate, UserData
from utilities.emojis import PancakeTypes, TreasureTypes, emojis
from utilities.localization.formatting import fnum, ftime
from utilities.localization.localization import Localization, locale_format
from utilities.localization.minis import put_mini
from utilities.message_decorations import Colors, fancy_message, make_progress_bar
from utilities.misc import make_empty_select
from utilities.nikogotchi_metadata import (
	NikogotchiMetadata,
	fetch_nikogotchi_metadata,
	pick_random_nikogotchi,
)


@dataclass
class TreasureSeekResults:
	found_treasure: Dict[TreasureTypes, int]
	total_treasure: int
	time_spent: timedelta


class NikogotchiCommands(Extension):
	async def get_nikogotchi(self, uid: str) -> Union[Nikogotchi, None]:
		data: Nikogotchi = await Nikogotchi(str(uid)).fetch()

		if data.status > -1:
			return data
		else:
			return None

	async def save_nikogotchi(self, nikogotchi: Nikogotchi, uid: str):
		nikogotchi_data: Nikogotchi = await Nikogotchi(str(uid)).fetch()

		await nikogotchi_data.update(**nikogotchi.__dict__)

	async def delete_nikogotchi(self, uid: str):
		nikogotchi_data = await Nikogotchi(str(uid)).fetch()

		await nikogotchi_data.update(available=False, status=-1, nid="?")

	async def nikogotchi_buttons(self, ctx, owner_id: str):
		prefix = "action_"
		suffix = f"_{owner_id}"

		loc = Localization(ctx, prefix="commands.nikogotchi")

		return [
			Button(
				style=ButtonStyle.SUCCESS,
				label=await locale_format(loc, loc.get("components.pet")),
				custom_id=f"{prefix}pet{suffix}",
			),
			Button(
				style=ButtonStyle.SUCCESS,
				label=await locale_format(loc, loc.get("components.clean")),
				custom_id=f"{prefix}clean{suffix}",
			),
			Button(
				style=ButtonStyle.PRIMARY,
				label=await locale_format(loc, loc.get("components.find_treasure")),
				custom_id=f"{prefix}findtreasure{suffix}",
			),
			Button(
				style=ButtonStyle.GREY,
				emoji=emojis["icons"]["refresh"],
				custom_id=f"{prefix}refresh{suffix}",
			),
			Button(style=ButtonStyle.DANGER, label="X", custom_id=f"{prefix}exit{suffix}"),
		]

	async def get_nikogotchi_age(self, uid: str):
		nikogotchi_data: Nikogotchi = await Nikogotchi(uid).fetch()

		return datetime.now() - nikogotchi_data.hatched

	async def get_main_embeds(
		self,
		ctx: InteractionContext,
		n: Nikogotchi,
		dialogue: str | None = None,
		treasure_seek_results: TreasureSeekResults | None = None,
		stats_update: List[StatUpdate] | None = None,
		preview: bool = False,
	) -> List[Embed] | Embed:
		metadata = await fetch_nikogotchi_metadata(n.nid)
		if not metadata:
			raise ValueError("Invalid Nikogotchi")
		owner = await ctx.client.fetch_user(n._id)
		if not owner:
			raise ValueError("Failed to fetch owner of Nikogotchi")
		loc = Localization(ctx, prefix="commands.nikogotchi")

		nikogotchi_status = await locale_format(loc, loc.get("status.normal"))

		if random.randint(0, 100) == 20:
			nikogotchi_status = await locale_format(loc, loc.get("status.normal-rare"))

		if n.happiness < 20:
			nikogotchi_status = await locale_format(loc, loc.get("status.pet"), name=n.name)

		if n.cleanliness < 20:
			nikogotchi_status = await locale_format(loc, loc.get("status.dirty"), name=n.name)

		if n.hunger < 20:
			nikogotchi_status = await locale_format(loc, loc.get("status.hungry"), name=n.name)
		treasure_looking = ""
		if n.status == 3:
			nikogotchi_status = await locale_format(loc, loc.get("status.treasure"), name=n.name)
			treasure_looking = f"\n-# 🎒  {ftime(datetime.now() - n.started_finding_treasure_at)}"

		treasure_found = ""
		if treasure_seek_results is not None:
			treasures = ""
			total = 0

			max_amount_length = len(
				fnum(
					max(treasure_seek_results.found_treasure.values(), default=0),
					locale=loc.locale,
				)
			)

			for tid, amount in treasure_seek_results.found_treasure.items():
				total += amount
				num = fnum(amount, loc.locale)
				rjust = num.rjust(max_amount_length, " ")
				treasures += (
					await locale_format(
						loc,
						loc.get("treasure.item", prefix_override="main"),
						spacer=rjust.replace(num, ""),
						amount=amount,
						icon=emojis["treasures"][tid],
						name=await locale_format(loc, loc.get(f"items.treasures.{tid}.name", prefix_override="main")),
					)
					+ "\n"
				)

			treasure_found = await locale_format(
				loc,
				loc.get("treasured.message"),
				treasures=treasures,
				total=total,
				time=ftime(treasure_seek_results.time_spent),
			)

		levelled_up_stats = ""

		if stats_update:
			for stat in stats_update:
				levelled_up_stats += (
					await locale_format(
						loc,
						loc.get("levelupped.stat"),
						icon=stat.icon,
						old_value=stat.old_value,
						new_value=stat.new_value,
						increase=(stat.new_value - stat.old_value),
					)
					+ "\n"
				)

		if n.health < min(20, n.max_health * 0.20):
			nikogotchi_status = await locale_format(loc, loc.get("status.danger"), name=n.name)

		# crafting embeds - - -
		embeds = []
		age = ftime(await self.get_nikogotchi_age(str(n._id)), minimum_unit="minute")
		age = f"  •  ⏰  {age}" if len(age) != 0 else ""

		def make_pb(current, maximum) -> str:
			return f"{make_progress_bar(current, maximum, 5, 'round')} ({current} / {maximum})"

		info = (
			f"❤️  {make_pb(n.health, n.max_health)}\n"
			+ f"⚡  {make_pb(n.energy, 5)}\n"
			+ "\n"
			+ f"🍴  {make_pb(n.hunger, n.max_hunger)}\n"
			+ f"🫂  {make_pb(n.happiness, n.max_happiness)}\n"
			+ f"🧽  {make_pb(n.cleanliness, n.max_cleanliness)}\n"
			+ "\n"
			+ f"-# 🏆  **{n.level}**  •  🗡️  **{n.attack}**  •  🛡️  **{n.defense}**"
			+ f"{treasure_looking}{age}"
		)

		if not preview:
			if dialogue:
				info += f"\n-# 💬 {dialogue}"
			else:
				info += f"\n-# 💭 {await locale_format(loc, loc.get('status.template'), status=nikogotchi_status)}"

		N_embed = Embed(
			title=f"{n.name} · *{n.pronouns}*" if n.pronouns != "/" else n.name,
			description=info,
			color=Colors.DEFAULT,
		)
		N_embed.set_thumbnail(metadata.image_url)

		if preview:
			N_embed.set_author(
				name=await locale_format(loc, loc.get("owned"), owner_id=owner.id),
				icon_url=owner.avatar_url,
			)
			return N_embed

		if levelled_up_stats:
			L_embed = Embed(
				title=await locale_format(loc, loc.get("levelupped.title"), level=n.level),
				description=await locale_format(loc, loc.get("levelupped.message"), stats=levelled_up_stats),
				color=Colors.GREEN,
			)
			embeds.append(L_embed)

		if treasure_found:
			T_embed = Embed(
				title=await locale_format(loc, loc.get("treasured.title")),
				description=treasure_found,
				color=Colors.GREEN,
			)
			embeds.append(T_embed)
		embeds.append(N_embed)
		return embeds

	@slash_command(description="All things about your Nikogotchi!")
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def nikogotchi(self, ctx: SlashContext):
		pass

	@nikogotchi.subcommand(sub_cmd_description="Check out your Nikogotchi!")
	async def check(self, ctx: SlashContext | ComponentContext):
		uid = ctx.author.id
		loc = Localization(ctx, prefix="commands.nikogotchi")

		nikogotchi: Nikogotchi = await Nikogotchi(uid).fetch()

		metadata = await fetch_nikogotchi_metadata(nikogotchi.nid)
		if nikogotchi.status > -1 and metadata:
			asyncio.create_task(ctx.defer())
			await fancy_message(
				ctx, await locale_format(loc, loc.get("generic.loading.nikogotchi", prefix_override="main")), edit=True
			)
		else:
			if not metadata and nikogotchi.nid != "?":
				buttons: list[BaseComponent | dict] = [
					Button(
						style=ButtonStyle.GREEN,
						label=await locale_format(loc, loc.get("other.error.buttons.rotate")),
						custom_id="rotate",
					),
					Button(
						style=ButtonStyle.GRAY,
						label=await locale_format(loc, loc.get("other.error.buttons.send_away")),
						custom_id="_rehome",
					),
				]

				await fancy_message(
					ctx,
					await locale_format(loc, loc.get("other.error.description"), id=nikogotchi.nid),
					color=Colors.BAD,
					ephemeral=True,
					components=buttons,
				)
				button_ctx = (await ctx.client.wait_for_component(components=buttons)).ctx

				custom_id = button_ctx.custom_id

				if custom_id == "_rehome":
					await self.delete_nikogotchi(str(ctx.author.id))
					return await ctx.edit(
						embed=Embed(
							description=await locale_format(
								loc,
								loc.get("other.send_away.success"),
								name=nikogotchi.name,
							),
							color=Colors.DEFAULT,
						),
						components=[],
					)
				else:
					nikogotchi.available = True
			if not nikogotchi.available:
				return await fancy_message(
					ctx,
					await locale_format(loc, loc.get("invalid"))
					+ await put_mini(
						loc,
						"minis.tips.no_nikogotchi",
						show_up_amount=5,
						type="tip",
						user_id=ctx.user.id,
						pre="\n\n",
					),
					ephemeral=True,
					color=Colors.BAD,
				)
			selected_nikogotchi: NikogotchiMetadata = await pick_random_nikogotchi(nikogotchi.rarity)

			await nikogotchi.update(
				nid=selected_nikogotchi.name,
				name=await locale_format(loc, loc.get(f"name.{selected_nikogotchi.name}")),
				level=0,
				health=50,
				energy=5,
				hunger=50,
				cleanliness=50,
				happiness=50,
				attack=5,
				defense=2,
				max_health=50,
				max_hunger=50,
				max_cleanliness=50,
				max_happiness=50,
				last_interacted=datetime.now(),
				hatched=datetime.now(),
				started_finding_treasure_at=datetime.now(),
				available=False,
				status=2,
				pronouns="it/its",
			)

			hatched_embed = Embed(
				title=await locale_format(loc, loc.get("found.title"), name=nikogotchi.name),
				color=Colors.GREEN,
				description=await locale_format(loc, loc.get("found.description"))
				+ await put_mini(loc, "minis.notes.rename", show_up_amount=5, user_id=ctx.user.id, pre="\n\n"),
			)

			hatched_embed.set_thumbnail(url=selected_nikogotchi.image_url)

			buttons = [
				Button(
					style=ButtonStyle.GREEN,
					label=await locale_format(loc, loc.get("other.renaming.button")),
					custom_id=f"rename {ctx.id}",
				),
				Button(
					style=ButtonStyle.GRAY,
					label=await locale_format(loc, loc.get("generic.buttons.continue", prefix_override="main")),
					custom_id=f"continue {ctx.id}",
				),
			]
			await ctx.send(
				embed=hatched_embed,
				components=buttons,
				ephemeral=True,
			)
			try:
				button: Component = await ctx.client.wait_for_component(components=buttons, timeout=15.0)
				if button.ctx.custom_id == f"rename {ctx.id}":
					await self.init_rename_flow(button.ctx, nikogotchi.name, True)
			except TimeoutError:
				return await self.check(ctx, edit=True)
		await self.nikogotchi_interaction(ctx)

	async def calculate_treasure_seek(self, uid: str, time_taken: timedelta) -> TreasureSeekResults | None:
		user_data: UserData = await UserData(_id=uid).fetch()

		amount = math.floor(time_taken.total_seconds() / 3600)

		if amount == 0:
			return None

		treasures_found = {}

		for _ in range(amount):
			value = random.randint(0, 5000)
			treasure_id = ""

			if value > 4900:
				treasure_id = random.choice(["die", "sun", "clover"])
			elif value > 3500:
				treasure_id = random.choice(["amber", "pen", "card"])
			elif value > 100:
				treasure_id = random.choice(["journal", "bottle", "shirt"])

			if treasure_id:
				treasures_found.setdefault(treasure_id, 0)
				treasures_found[treasure_id] += 1

		await user_data.update(owned_treasures=Counter(user_data.owned_treasures) + Counter(treasures_found))
		return TreasureSeekResults(treasures_found, amount, time_taken)

	r_nikogotchi_interaction = re.compile(r"action_(feed|pet|clean|findtreasure|refresh|callback|exit)_(\d+)$")

	@component_callback(r_nikogotchi_interaction)
	async def nikogotchi_interaction(self, ctx: ComponentContext):
		try:
			await ctx.defer(edit_origin=True)

			match = self.r_nikogotchi_interaction.match(ctx.custom_id)

			if not match:
				return

			custom_id = match.group(1)
			uid = match.group(2)

			if str(ctx.author.id) != uid:
				return
		except:
			uid = str(ctx.author.id)
			custom_id = "refresh"

		if custom_id == "exit":
			await ctx.delete()

		loc = Localization(ctx, prefix="commands.nikogotchi")

		nikogotchi = await self.get_nikogotchi(str(uid))

		if nikogotchi is None:
			return await ctx.edit_origin(
				embed=Embed(
					description=await locale_format(loc, loc.get("other.you_invalid")),
					color=Colors.BAD,
				),
				components=Button(
					emoji=emojis["icons"]["refresh"],
					custom_id=f"action_refresh_{ctx.author.id}",
					style=ButtonStyle.SECONDARY,
				),
			)

		last_interacted = nikogotchi.last_interacted

		if not nikogotchi.started_finding_treasure_at:
			await nikogotchi.update(started_finding_treasure_at=datetime.now())

		current_time = datetime.now()

		time_difference = (current_time - last_interacted).total_seconds() / 3600

		age = await self.get_nikogotchi_age(str(ctx.author.id))

		await nikogotchi.update(last_interacted=current_time)

		modifier = 1

		if nikogotchi.status == 3:
			modifier = 2.5

		random_stat_modifier = random.uniform(1, 1.50)

		nikogotchi.hunger = round(max(0, nikogotchi.hunger - time_difference * random_stat_modifier * modifier))

		random_stat_modifier = random.uniform(1, 1.50)

		nikogotchi.happiness = round(
			max(
				0,
				nikogotchi.happiness - time_difference * random_stat_modifier * modifier,
			)
		)

		random_stat_modifier = random.uniform(1, 1.50)

		nikogotchi.cleanliness = round(
			max(
				0,
				nikogotchi.cleanliness - time_difference * random_stat_modifier * modifier,
			)
		)

		if nikogotchi.hunger <= 0 or nikogotchi.happiness <= 0 or nikogotchi.cleanliness <= 0:
			nikogotchi.health = round(nikogotchi.health - time_difference * 0.5)

		if nikogotchi.health <= 0:
			age = ftime(age)
			embed = Embed(
				title=await locale_format(loc, loc.get("died.title"), name=nikogotchi.name),
				color=Colors.DARKER_WHITE,
				description=await locale_format(
					loc,
					loc.get("died.description"),
					name=nikogotchi.name,
					age=age,
					time_difference=fnum(int(time_difference)),
				),
			)

			await self.delete_nikogotchi(str(uid))

			try:
				await ctx.edit_origin(embed=embed, components=[])
			except:
				await ctx.edit(embed=embed, components=[])
			return

		dialogue = ""
		treasures_found = None
		buttons = await self.nikogotchi_buttons(ctx, str(uid))
		select = await self.make_food_select(loc, nikogotchi, f"feed_food {ctx.user.id}")

		if nikogotchi.status == 2:
			if custom_id == "pet":
				happiness_increase = 20
				nikogotchi.happiness = min(nikogotchi.max_happiness, nikogotchi.happiness + happiness_increase)
				dialogue = random.choice(
					await locale_format(loc, loc.get(f"dialogue.{nikogotchi.nid}.pet", typecheck=tuple))
				)

			if custom_id == "clean":
				cleanliness_increase = 30
				nikogotchi.cleanliness = min(
					nikogotchi.max_cleanliness,
					nikogotchi.cleanliness + cleanliness_increase,
				)
				dialogue = random.choice(
					await locale_format(loc, loc.get(f"dialogue.{nikogotchi.nid}.cleaned", typecheck=tuple))
				)

			if custom_id == "findtreasure":
				dialogue = await locale_format(loc, loc.get("treasured.dialogues.sent")) + await put_mini(
					loc,
					"minis.notes.sent_treasure",
					user_id=ctx.user.id,
					show_up_amount=25,
					pre="\n\n",
				)
				nikogotchi.status = 3
				nikogotchi.started_finding_treasure_at = datetime.now()

		if custom_id == "callback" and nikogotchi.status == 3:
			treasures_found = await self.calculate_treasure_seek(
				str(uid), datetime.now() - nikogotchi.started_finding_treasure_at
			)
			nikogotchi.status = 2
			print(datetime.now(), ctx.author_id, treasures_found)
			if treasures_found is None:
				dialogue = await locale_format(loc, loc.get("treasured.dialogues.none_found"))

		embeds = await self.get_main_embeds(ctx, nikogotchi, dialogue, treasure_seek_results=treasures_found)

		if not custom_id == "feed":
			if nikogotchi.status == 2:
				buttons[0].disabled = False
				buttons[1].disabled = False
				buttons[2].disabled = False

				buttons[2].label = str(await locale_format(loc, loc.get("components.find_treasure")))
				buttons[2].custom_id = f"action_findtreasure_{uid}"
			else:
				select.disabled = True
				buttons[0].disabled = True
				buttons[1].disabled = True
				buttons[2].disabled = False

				buttons[2].label = str(await locale_format(loc, loc.get("components.call_back")))
				buttons[2].custom_id = f"action_callback_{uid}"
		try:
			await ctx.edit_origin(embeds=embeds, components=[ActionRow(select), ActionRow(*buttons)])
		except:
			await ctx.edit(embeds=embeds, components=[ActionRow(select), ActionRow(*buttons)])
		await self.save_nikogotchi(nikogotchi, str(ctx.author.id))

	async def make_food_select(self, loc, data: Nikogotchi, custom_id: str):
		if all(getattr(data, attr) <= 0 for attr in ["glitched_pancakes", "golden_pancakes", "pancakes"]):
			return await make_empty_select(
				loc, placeholder=await locale_format(loc, loc.get_string("components.feed.no_food"))
			)

		# name_map = {  # TODO: rm this when db fix
		# 	"glitched_pancakes": "glitched",
		# 	"golden_pancakes": "golden",
		# 	"pancakes": "normal",
		# }
		select = StringSelectMenu(
			custom_id=custom_id,
			placeholder=await locale_format(loc, loc.get_string("components.feed.placeholder"), name=data.name),
		)
		for pancake in ("glitched_pancakes", "golden_pancakes", "pancakes"):
			updated_name: PancakeTypes = pancake_id_to_emoji_index_please_rename_them_in_db(pancake)
			amount = getattr(data, pancake)
			if amount <= 0:
				continue
			select.options.append(
				StringSelectOption(
					label=await locale_format(loc, loc.get_string(f"components.feed.{pancake}"), amount=amount),
					emoji=emojis["pancakes"][updated_name],
					value=updated_name,
				)
			)
		return select

	ff = re.compile(r"feed_food (\d+)$")

	@component_callback(ff)
	async def feed_food(self, ctx: ComponentContext):
		await ctx.defer(edit_origin=True)

		match = self.ff.match(ctx.custom_id)
		if not match:
			return
		uid = int(match.group(1))

		if ctx.author.id != uid:
			return await ctx.edit()

		nikogotchi: Nikogotchi | None = await self.get_nikogotchi(str(uid))
		if not nikogotchi:
			return
		pancake_type = ctx.values[0]

		normal_pancakes = nikogotchi.pancakes
		golden_pancakes = nikogotchi.golden_pancakes
		glitched_pancakes = nikogotchi.glitched_pancakes

		hunger_increase = 0
		health_increase = 0

		updated_stats = []

		loc = Localization(ctx, prefix="commands.nikogotchi")

		match pancake_type:
			case "golden":
				if golden_pancakes <= 0:
					dialogue = await locale_format(loc, loc.get("components.feed.invalid"))
				else:
					hunger_increase = 50
					health_increase = 25

					golden_pancakes -= 1
				dialogue = random.choice(
					await locale_format(loc, loc.get(f"dialogue.{nikogotchi.nid}.fed", typecheck=tuple))
				)
			case "glitched":
				if glitched_pancakes <= 0:
					dialogue = await locale_format(loc, loc.get("components.feed.invalid"))
				else:
					hunger_increase = 9999
					health_increase = 9999

					glitched_pancakes -= 1
					updated_stats = await nikogotchi.level_up(5)
					dialogue = await locale_format(loc, loc.get("components.feed.glitched_powerup"))
			case "normal":
				if normal_pancakes <= 0:
					dialogue = await locale_format(loc, loc.get("components.feed.invalid"))
				else:
					hunger_increase = 25
					health_increase = 1

					normal_pancakes -= 1
					dialogue = random.choice(
						await locale_format(loc, loc.get(f"dialogue.{nikogotchi.nid}.fed", typecheck=tuple))
					)
			case _:
				return await ctx.edit()

		nikogotchi = await nikogotchi.update(
			pancakes=normal_pancakes,
			golden_pancakes=golden_pancakes,
			glitched_pancakes=glitched_pancakes,
		)

		nikogotchi.hunger = min(nikogotchi.max_hunger, nikogotchi.hunger + hunger_increase)
		nikogotchi.health = min(nikogotchi.max_health, nikogotchi.health + health_increase)

		await self.save_nikogotchi(nikogotchi, str(ctx.author.id))

		buttons = await self.nikogotchi_buttons(ctx, str(ctx.author.id))
		select = await self.make_food_select(loc, nikogotchi, f"feed_food {ctx.user.id}")

		embeds = await self.get_main_embeds(ctx, nikogotchi, dialogue, stats_update=updated_stats)

		await ctx.edit_origin(embeds=embeds, components=[ActionRow(select), ActionRow(*buttons)])

	@nikogotchi.subcommand(sub_cmd_description="Part ways with your Nikogotchi")
	async def send_away(self, ctx: SlashContext):
		loc = Localization(ctx, prefix="commands.nikogotchi")

		nikogotchi = await self.get_nikogotchi(str(ctx.author.id))

		if nikogotchi is None:
			return await fancy_message(
				ctx,
				await locale_format(loc, loc.get("other.you_invalid")),
				ephemeral=True,
				color=Colors.BAD,
			)

		name = nikogotchi.name

		buttons: list[BaseComponent | dict] = [
			Button(
				style=ButtonStyle.RED,
				label=await locale_format(loc, loc.get("generic.buttons.yes", prefix_override="main")),
				custom_id="rehome",
			),
			Button(
				style=ButtonStyle.GRAY,
				label=await locale_format(loc, loc.get("generic.buttons.cancel", prefix_override="main")),
				custom_id="cancel",
			),
		]

		await ctx.send(
			embed=Embed(
										description=await locale_format(loc, loc.get("other.send_away.description"), name=name),
				color=Colors.WARN,
			),
			ephemeral=True,
			components=buttons,
		)

		button = await ctx.client.wait_for_component(components=buttons)
		button_ctx = button.ctx

		custom_id = button_ctx.custom_id

		if custom_id == "rehome":
			await self.delete_nikogotchi(str(ctx.author.id))
			await ctx.edit(
				embed=Embed(
					description=await locale_format(loc, loc.get("other.send_away.success"), name=name),
					color=Colors.GREEN,
				),
				components=[],
			)
		else:
			await ctx.delete()

	async def init_rename_flow(self, ctx: ComponentContext | SlashContext, old_name: str, cont: bool = False):
		loc = Localization(ctx, prefix="commands.nikogotchi")
		modal = Modal(
			ShortText(
				custom_id="name",
				value=old_name,
				label=await locale_format(loc, loc.get("other.renaming.input.label")),
				placeholder=await locale_format(loc, loc.get("other.renaming.input.placeholder")),
				max_length=32,
			),
			custom_id="rename_nikogotchi",
			title=await locale_format(loc, loc.get("other.renaming.title")),
		)
		if cont:
			modal.custom_id = "rename_nikogotchi continue"
		await ctx.send_modal(modal)

	@modal_callback(re.compile(r"rename_nikogotchi?.+"))
	async def on_rename_answer(self, ctx: ModalContext, name: str):
		loc = Localization(ctx, prefix="commands.nikogotchi")

		if ctx.custom_id.endswith("continue"):
			await ctx.defer(edit_origin=True)
		else:
			await ctx.defer(ephemeral=True)
		nikogotchi = await self.get_nikogotchi(str(ctx.author.id))
		if nikogotchi is None:
			return await fancy_message(
				ctx,
				await locale_format(loc, loc.get("other.you_invalid_get")),
				ephemeral=True,
				color=Colors.BAD,
			)

		old_name = nikogotchi.name
		nikogotchi.name = name
		await self.save_nikogotchi(nikogotchi, str(ctx.author.id))
		components = []
		if ctx.custom_id.endswith("continue"):
			components.append(
				Button(
					style=ButtonStyle.GRAY,
					label=await locale_format(loc, loc.get("generic.buttons.continue", prefix_override="main")),
					custom_id=f"action_refresh_{ctx.author_id}",
				)
			)
		await fancy_message(
			ctx,
			await locale_format(loc, loc.get("other.renaming.response"), new_name=name, old_name=old_name),
			ephemeral=True,
			components=components,
		)

	@nikogotchi.subcommand(sub_cmd_description="Rename your Nikogotchi")
	async def rename(self, ctx: SlashContext):
		loc = Localization(ctx, prefix="commands.nikogotchi")
		nikogotchi = await self.get_nikogotchi(str(ctx.author.id))

		if nikogotchi is None:
			return await fancy_message(
				ctx,
				await locale_format(loc, loc.get("other.you_invalid_get")),
				ephemeral=True,
				color=Colors.BAD,
			)

		return await self.init_rename_flow(ctx, nikogotchi.name)

	@nikogotchi.subcommand(sub_cmd_description="Show off a nikogotchi in chat")
	@slash_option(
		"user",
		description="Who's nikogotchi would you like to see?",
		opt_type=OptionType.USER,
	)
	async def show(self, ctx: SlashContext, user: User | None = None):
		loc = Localization(ctx, prefix="commands.nikogotchi")
		if user is None:
			user = ctx.user

		nikogotchi = await self.get_nikogotchi(str(user.id))

		if nikogotchi is None:
			return await fancy_message(
				ctx,
				await locale_format(loc, loc.get("other.other_invalid")),
				ephemeral=True,
				color=Colors.BAD,
			)

		await ctx.send(embeds=await self.get_main_embeds(ctx, nikogotchi, preview=True))

	@nikogotchi.subcommand(sub_cmd_description="Trade your Nikogotchi with someone else!")
	@slash_option("user", description="The user to trade with.", opt_type=OptionType.USER, required=True)
	async def trade(self, ctx: SlashContext, user: User):
		loc = Localization(ctx, prefix="commands.nikogotchi")

		try:
			nikogotchi_one = await self.get_nikogotchi(str(ctx.author.id))
			assert nikogotchi_one is not None
			one_data = await fetch_nikogotchi_metadata(nikogotchi_one.nid)
			assert one_data is not None
		except:
			return await fancy_message(
				ctx, await locale_format(loc, loc.get("other.you_invalid")), ephemeral=True, color=Colors.BAD
			)

		try:
			nikogotchi_two = await self.get_nikogotchi(str(user.id))
			assert nikogotchi_two is not None
			two_data = await fetch_nikogotchi_metadata(nikogotchi_two.nid)
			assert two_data is not None
		except:
			return await fancy_message(
				ctx,
				await locale_format(loc, loc.get("other.other_invalid")),
				ephemeral=True,
				color=Colors.BAD,
			)

		await fancy_message(
			ctx,
			await locale_format(loc, loc.get("other.trade.waiting"), receiver_id=user.id),
			ephemeral=True,
		)

		uid = user.id

		buttons = [
			Button(
				style=ButtonStyle.DANGER,
				label=await locale_format(loc, loc.get("generic.buttons.accept", prefix_override="main")),
				custom_id=f"accept {ctx.author.id} {uid}",
			),
			Button(
				style=ButtonStyle.SECONDARY,
				label=await locale_format(loc, loc.get("generic.buttons.decline", prefix_override="main")),
				custom_id=f"decline {ctx.author.id} {uid}",
			),
		]

		await user.send(
			embed=Embed(
				description=await locale_format(
					loc,
					loc.get("other.trade.request"),
					sender_id=ctx.author.id,
					receiver_id=user.id,
					sender_nikogotchi_name=nikogotchi_one.name,
					receiver_nikogotchi_name=nikogotchi_two.name,
				),
				color=Colors.WARN,
			),
			components=buttons,
		)

		button = await ctx.client.wait_for_component(components=buttons)
		button_ctx = button.ctx

		await button_ctx.defer(edit_origin=True)

		custom_id = button_ctx.custom_id

		if custom_id == f"accept {ctx.author.id} {uid}":
			del nikogotchi_two._id
			del nikogotchi_one._id
			await self.save_nikogotchi(nikogotchi_two, str(ctx.author.id))
			await self.save_nikogotchi(nikogotchi_one, str(uid))
			nikogotchi_two._id = str(ctx.author.id)
			nikogotchi_one._id = str(uid)
			embed_two = Embed(
				description=await locale_format(
					loc,
					loc.get("other.trade.success"),
					user_id=user.id,
					received_nikogotchi_name=nikogotchi_two.name,
				),
				color=Colors.GREEN,
			)
			embed_two.set_image(url=two_data.image_url)

			embed_one = Embed(
				description=await locale_format(
					loc,
					loc.get("other.trade.success"),
					user_id=ctx.author.id,
					received_nikogotchi_name=nikogotchi_one.name,
				),
				color=Colors.GREEN,
			)
			embed_one.set_image(url=one_data.image_url)

			await button_ctx.edit_origin(embed=embed_one, components=[])
			await ctx.edit(embed=embed_two)
		else:
			sender_embed = Embed(
				description=await locale_format(loc, loc.get("other.trade.declined")),
				color=Colors.RED,
			)
			receiver_embed = Embed(
				description=await locale_format(loc, loc.get("other.trade.success_decline")),
				color=Colors.RED,
			)
			await asyncio.gather(ctx.edit(embed=sender_embed), button_ctx.edit_origin(embed=receiver_embed, components=[]))

	async def init_repronoun_flow(
		self,
		ctx: ComponentContext | SlashContext,
		old_pronouns: str,
		cont: bool = False,
	):
		loc = Localization(ctx, prefix="commands.nikogotchi")
		modal = Modal(
			ShortText(
				custom_id="pronouns",
				value=old_pronouns,
				label=await locale_format(loc, loc.get("other.repronoun.input.label")),
				placeholder=await locale_format(loc, loc.get("other.repronoun.input.placeholder")),
				max_length=32,
			),
			custom_id="repronoun_nikogotchi",
			title=await locale_format(loc, loc.get("other.repronoun.title")),
		)
		if cont:
			modal.custom_id = "repronoun_nikogotchi continue"
		await ctx.send_modal(modal)

	@modal_callback(re.compile(r"repronoun_nikogotchi?.+"))
	async def on_repronoun_answer(self, ctx: ModalContext, pronouns: str):
		loc = Localization(ctx, prefix="commands.nikogotchi")

		if ctx.custom_id.endswith("continue"):
			await ctx.defer(edit_origin=True)
		else:
			await ctx.defer(ephemeral=True)
		nikogotchi = await self.get_nikogotchi(str(ctx.author.id))
		if nikogotchi is None:
			return await fancy_message(
				ctx,
				await locale_format(loc, loc.get("other.you_invalid_get")),
				ephemeral=True,
				color=Colors.BAD,
			)
		if pronouns != "/" and ("/" not in pronouns or not all(pronouns.split("/"))):
			return await fancy_message(
				ctx,
				await locale_format(loc, loc.get("other.insufficient_pronouns")),
				ephemeral=True,
				color=Colors.BAD,
			)
		old_pronouns = nikogotchi.pronouns
		nikogotchi.pronouns = pronouns
		await self.save_nikogotchi(nikogotchi, str(ctx.author.id))
		components = []
		if ctx.custom_id.endswith("continue"):
			components.append(
				Button(
					style=ButtonStyle.GRAY,
					label=await locale_format(loc, loc.get("generic.buttons.continue", prefix_override="main")),
					custom_id=f"action_refresh_{ctx.author_id}",
				)
			)
		await fancy_message(
			ctx,
			await locale_format(
				loc,
				loc.get("other.repronoun.response"),
				new_pronouns=pronouns,
				old_pronouns=old_pronouns,
			),
			ephemeral=True,
			components=components,
		)

	@nikogotchi.subcommand(sub_cmd_description="Change the pronouns of your nikogotchi")
	async def repronoun(self, ctx: SlashContext):
		loc = Localization(ctx, prefix="commands.nikogotchi")
		nikogotchi = await self.get_nikogotchi(str(ctx.author.id))

		if nikogotchi is None:
			return await fancy_message(
				ctx,
				await locale_format(loc, loc.get("other.you_invalid_get")),
				ephemeral=True,
				color=Colors.BAD,
			)

		return await self.init_repronoun_flow(ctx, nikogotchi.pronouns)
