import asyncio
import random
import re
from collections import Counter
from dataclasses import asdict
from typing import Literal, get_args

from interactions import (
	ActionRow,
	Button,
	ButtonStyle,
	ComponentContext,
	Embed,
	EmbedAttachment,
	Extension,
	PartialEmoji,
	SlashContext,
	StringSelectMenu,
	StringSelectOption,
	component_callback,
	contexts,
	integration_types,
	listen,
	slash_command,
)
from interactions.api.events import Ready

from utilities.database.schemas import Nikogotchi, UserData
from utilities.emojis import emojis
from utilities.localization.localization import Localization, locale_format
from utilities.message_decorations import Colors, fancy_message
from utilities.shop.fetch_items import fetch_background, fetch_item, fetch_treasure
from utilities.shop.fetch_shop_data import (
	Item,
	TreasureTypes,
	get_shop_data,
)


def pancake_id_to_emoji_index_please_rename_them_in_db(
	pancake_id: Literal["pancakes", "golden_pancakes", "glitched_pancakes"],
):
	if pancake_id == "pancakes":
		return "normal"
	elif pancake_id == "golden_pancakes":
		return "golden"
	elif pancake_id == "glitched_pancakes":
		return "glitched"


class ShopCommands(Extension):
	max_buy_sell_limit = 555
	max_wool_limit = 300_000

	@listen(Ready)
	async def loadde_shoppe(self, event: Ready):
		await self.get_shop()

	async def get_shop(self):
		return await get_shop_data()

	@component_callback("select_treasure_sell")
	async def select_treasure_sell_callback(self, ctx: ComponentContext):
		await ctx.defer(edit_origin=True)

		await self.get_shop()

		treasure = ctx.values[0]

		embeds, components = await self.embed_manager(ctx, "Sell_Treasures", selected_treasure=treasure)

		await ctx.edit(embeds=embeds, components=components)

	@component_callback("select_treasure")
	async def select_treasure_callback(self, ctx: ComponentContext):
		await ctx.defer(edit_origin=True)

		await self.get_shop()

		treasure = ctx.values[0]

		embeds, components = await self.embed_manager(ctx, "Treasures", selected_treasure=treasure)

		await ctx.edit(embeds=embeds, components=components)

	@component_callback("sell_treasure_menu")
	async def sell_treasure_callback(self, ctx: ComponentContext):
		await ctx.defer(edit_origin=True)

		await self.get_shop()

		embeds, components = await self.embed_manager(ctx, "Sell_Treasures", selected_treasure=None)

		await ctx.edit(embeds=embeds, components=components)

	r_treasure_sell = re.compile(r"treasure_sell_(.*)_(.*)")

	@component_callback(r_treasure_sell)
	async def treasure_sell_action_callback(self, ctx: ComponentContext):
		daily_shop = await self.get_shop()

		await ctx.defer(edit_origin=True)

		base_loc = Localization(ctx, prefix="commands.shop.base")
		items_loc = Localization(ctx, prefix="items")

		await self.get_shop()

		match = self.r_treasure_sell.search(ctx.custom_id)

		if not match:
			return
		raw_tid: str = match.group(1)
		if raw_tid not in get_args(TreasureTypes):
			raise ValueError(f"Unknown treasure type: {raw_tid}")
		treasure_id: TreasureTypes = raw_tid  # type:ignore
		amount_to_sell = match.group(2)

		stock_price = daily_shop.stock.price

		user_data: UserData = await UserData(_id=ctx.author.id).fetch()

		all_treasures = await fetch_treasure()
		owned_treasure = Counter(user_data.owned_treasures)

		amount_of_treasure = owned_treasure[treasure_id]

		treasure = all_treasures[treasure_id]

		result_text = ""

		treasure_loc: dict = await locale_format(items_loc, items_loc.get(f"treasure.{treasure_id}", typecheck=dict))

		async def update():
			embeds, components = await self.embed_manager(ctx, "Sell_Treasures", selected_treasure=treasure_id)

			embeds[0].set_footer(result_text)

			await ctx.edit(embeds=embeds, components=components)

		if amount_of_treasure <= 0:
			result_text = await locale_format(base_loc, base_loc.get("responses.errors.generic_trade_fail"))
			await update()
			return

		sell_price_one = int(treasure["price"] * stock_price)

		# allow to sell atleast one item
		max_allowed = max(1, min(self.max_buy_sell_limit, self.max_wool_limit // max(1, sell_price_one)))
		limit_reached = None

		if amount_to_sell == "all":
			amount = min(int(amount_of_treasure), max_allowed)
			if amount_of_treasure > max_allowed:
				limit_reached = "yes"

			sell_price = int(amount * sell_price_one)
			owned_treasure[treasure_id] -= amount
		else:
			amount = 1
			sell_price = sell_price_one
			owned_treasure[treasure_id] -= 1

		await user_data.update(owned_treasures=owned_treasure)
		result_text = await locale_format(
			base_loc,
			base_loc.get("responses.selling.success"),
			item_name=treasure_loc["name"],
			amount=amount,
			price=sell_price,
			limit_reached=limit_reached,
		)

		await user_data.manage_wool(sell_price)

		await update()

	r_treasure_buy = re.compile(r"treasure_buy_(.*)_(.*)")

	@component_callback(r_treasure_buy)
	async def buy_treasure_callback(self, ctx: ComponentContext):
		daily_shop = await self.get_shop()

		await ctx.defer(edit_origin=True)

		base_loc = Localization(ctx, prefix="commands.shop.base")
		items_loc = Localization(ctx, prefix="items")

		await self.get_shop()

		user_data: UserData = await UserData(_id=ctx.author.id).fetch()

		match = self.r_treasure_buy.match(ctx.custom_id)

		if not match:
			return

		raw_tid: str = match.group(1)
		if raw_tid not in get_args(TreasureTypes):
			raise ValueError(f"Unknown treasure type: {raw_tid}")
		treasure_id: TreasureTypes = raw_tid  # type:ignore
		amount_to_buy = match.group(2)

		all_treasures = await fetch_treasure()

		treasure = all_treasures[treasure_id]

		treasure_price = int(treasure["price"] * daily_shop.stock.price)

		async def update(text: str):
			embeds, components = await self.embed_manager(ctx, "Treasures", selected_treasure=treasure_id)
			embeds[0].set_footer(text)

			await ctx.edit(embeds=embeds, components=components)

		if user_data.wool < treasure_price:
			return await update(await locale_format(base_loc, base_loc.get("responses.errors.generic_trade_fail")))

		current_balance = user_data.wool
		max_allowed = max(1, min(self.max_buy_sell_limit, self.max_wool_limit // max(1, treasure_price)))
		limit_reached = None

		treasure_loc: dict = await locale_format(items_loc, items_loc.get(f"treasure.{treasure_id}", typecheck=dict))
		name = treasure_loc["name"]

		if amount_to_buy == "All":
			affordable = current_balance // max(1, treasure_price)
			amount = min(affordable, max_allowed)

			if affordable > max_allowed:
				limit_reached = "yes"

			price = treasure_price * amount
		else:
			price = int(treasure_price)
			amount = 1

		owned_treasure = Counter(user_data.owned_treasures)

		owned_treasure[treasure_id] = owned_treasure.get(treasure_id, 0) + amount

		await user_data.update(owned_treasures=owned_treasure)
		await user_data.manage_wool(-price)

		return await update(
			await locale_format(
				base_loc,
				base_loc.get("responses.buying.success"),
				item_name=name,
				amount=int(amount),
				price=int(price),
				limit_reached=limit_reached,
			)
		)

	r_buy_bg = re.compile(r"buy_bg_(.*)_(\d+)")

	@component_callback(r_buy_bg)
	async def backgrounds_callback(self, ctx: ComponentContext):
		base_loc = Localization(ctx, prefix="commands.shop.base")
		backgrounds_loc = Localization(ctx, prefix="commands.shop.backgrounds")
		await ctx.defer(edit_origin=True)

		user: UserData = await UserData(_id=ctx.author.id).fetch()

		match = self.r_buy_bg.match(ctx.custom_id)

		if not match:
			return

		bg_id = match.group(1)
		page = int(match.group(2))

		all_bgs = await fetch_background()
		get_background = all_bgs[bg_id]

		owned_backgrounds = user.owned_backgrounds

		embeds, components = await self.embed_manager(ctx, "Backgrounds", page=page)
		if bg_id in owned_backgrounds:
			embeds[0].set_footer(await locale_format(base_loc, base_loc.get("buttons.owned")))
		elif user.wool < get_background["price"]:
			embeds[0].set_footer(await locale_format(base_loc, base_loc.get("buttons.cannot_afford.single")))
		else:
			await owned_backgrounds.append(bg_id)

			embeds[0].description = await locale_format(
				backgrounds_loc,
				backgrounds_loc.get("newly_owned"),
				user_wool=await locale_format(base_loc, base_loc.get("user_wool"), wool=user.wool),
			)
			await user.manage_wool(-get_background["price"])
			embeds[0].set_footer(await locale_format(backgrounds_loc, backgrounds_loc.get("traded")))
		await ctx.send(embeds=embeds, components=components, ephemeral=True)

	@component_callback("nikogotchi_buy")
	async def buy_nikogotchi_callback(self, ctx: ComponentContext):
		await ctx.defer(edit_origin=True)

		base_loc = Localization(ctx, prefix="commands.shop.base")
		capsules_loc = Localization(ctx, prefix="commands.shop.capsules")
		items_loc = Localization(ctx, prefix="items")

		user_data: UserData = await UserData(_id=ctx.author.id).fetch()
		nikogotchi: Nikogotchi = await Nikogotchi(_id=ctx.author.id).fetch()

		capsules = await fetch_item()
		capsules = capsules["capsules"]
		capsule_id = random.choices(range(0, 4), weights=[0.40, 0.30, 0.20, 0.10], k=1)[0]

		nikogotchi_capsule = Item(**capsules[capsule_id])
		capsule_loc = await locale_format(items_loc, items_loc.get(f"capsule.{nikogotchi_capsule.id}"))

		async def update(result: str):
			embeds, components = await self.embed_manager(ctx, "capsules")
			embeds[0].set_footer(result)

			await ctx.edit(embeds=embeds, components=components)

		if nikogotchi.status > -1 or nikogotchi.available:
			return await update(await locale_format(base_loc, base_loc.get("responses.errors.generic_trade_fail")))

		if user_data.wool < nikogotchi_capsule.cost:
			return await update(await locale_format(base_loc, base_loc.get("responses.errors.generic_trade_fail")))

		await nikogotchi.update(available=True, rarity=capsule_id)
		await user_data.manage_wool(-50_000)

		await update(
			await locale_format(capsules_loc, capsules_loc.get("result.message"), amount=50_000, capsule_name=capsule_loc)
		)

	r_buy_object = re.compile(r"buy_([^\d]+)_(\d+)")

	@component_callback(r_buy_object)
	async def buy_pancakes_callback(self, ctx: ComponentContext):
		await ctx.defer(edit_origin=True)

		base_loc = Localization(ctx, prefix="commands.shop.base")
		items_loc = Localization(ctx, prefix="items")

		user_data: UserData = await UserData(_id=ctx.author.id).fetch()
		nikogotchi_data: Nikogotchi = await Nikogotchi(_id=ctx.author.id).fetch()

		match = self.r_buy_object.match(ctx.custom_id)

		if not match:
			return

		item_category = match.group(1)
		item_id = int(match.group(2))

		result_text = ""

		async def update():
			embeds, components = await self.embed_manager(ctx, item_category)
			embeds[0].set_footer(result_text)

			return await ctx.edit(embeds=embeds, components=components)

		item = await fetch_item()
		item = item["pancakes"][item_id]
		item = Item(**item)

		item_loc: dict = await locale_format(
			items_loc,
			items_loc.get(f"pancake.{pancake_id_to_emoji_index_please_rename_them_in_db(item.id)}", typecheck=dict),
		)

		if user_data.wool < item.cost:
			result_text = await locale_format(base_loc, base_loc.get("responses.errors.generic_trade_fail"))
			return await update()

		result_text = await locale_format(
			base_loc, base_loc.get("responses.buying.success"), amount=1, item_name=item_loc["name"]
		)

		json_data = asdict(nikogotchi_data)

		await nikogotchi_data.update(**{item.id: json_data[item.id] + 1})

		await user_data.manage_wool(-item.cost)
		await update()

	@component_callback("capsules", "pancakes", "Backgrounds", "Treasures", "go_back")
	async def main_shop_callbacks(self, ctx: ComponentContext):
		await ctx.defer(edit_origin=True)

		await self.get_shop()

		embeds, components = await self.embed_manager(ctx, ctx.custom_id, page=0)
		await ctx.edit(embeds=embeds, components=components)

	r_page = re.compile(r"page_([^\d]+)_(\d+)")

	@component_callback(r_page)
	async def page_callback(self, ctx: ComponentContext):
		loc = Localization(ctx, prefix="commands.shop.base")
		loading = asyncio.create_task(fancy_message(ctx, await locale_format(loc, loc.get("loading")), edit_origin=True))

		daily_shop = await self.get_shop()

		match = self.r_page.match(ctx.custom_id)

		if not match:
			return

		action = match.group(1)
		bg_page = int(match.group(2))

		bgs = daily_shop.background_stock

		if action == "prev":
			if bg_page > 0:
				bg_page -= 1
			else:
				bg_page = len(bgs) - 1

		if action == "next":
			if bg_page < len(bgs) - 1:
				bg_page += 1
			else:
				bg_page = 0

		embeds, components = await self.embed_manager(ctx, "Backgrounds", page=bg_page)
		await loading
		await ctx.edit(embeds=embeds, components=components)

	## EMBED MANAGER ---------------------------------------------------------------

	async def embed_manager(self, ctx: SlashContext | ComponentContext, category: str, **kwargs):
		daily_shop = await self.get_shop()

		base_loc = Localization(ctx, prefix="commands.shop.base")

		user_data: UserData = await UserData(_id=ctx.author.id).fetch()

		wool: int = user_data.wool

		user_wool = await locale_format(base_loc, base_loc.get("user_wool"), wool=user_data.wool)
		magpie_image = EmbedAttachment("https://cdn.discordapp.com/emojis/1394387803718029364.webp")

		go_back = Button(
			style=ButtonStyle.GRAY,
			custom_id="go_back",
			label=await locale_format(base_loc, base_loc.get("buttons.go_back")),
		)

		b_owned: str = await locale_format(base_loc, base_loc.get("buttons.owned"))
		b_poor: str = await locale_format(base_loc, base_loc.get("buttons.cannot_afford.single"))
		embeds = []
		components = []

		loc = Localization(ctx, prefix="commands.shop.main")
		capsules_loc = Localization(ctx, prefix="commands.shop.capsules")
		pancakes_loc = Localization(ctx, prefix="commands.shop.pancakes")
		backgrounds_loc = Localization(ctx, prefix="commands.shop.backgrounds")
		treasures_loc = Localization(ctx, prefix="commands.shop.treasures")
		items_loc = Localization(ctx, prefix="items")
		if category == "main_shop" or category == "go_back":
			motds: tuple = await locale_format(loc, loc.get("motds", typecheck=tuple))

			motd = motds[daily_shop.motd]

			embeds.append(
				Embed(
					title=await locale_format(loc, loc.get("title")),
					description=await locale_format(loc, loc.get("description"), motd=motd, user_wool=user_wool),
					thumbnail=magpie_image,
					color=Colors.SHOP,
				)
			)

			buttons = [
				Button(
					label=await locale_format(capsules_loc, capsules_loc.get("title")),
					emoji=emojis["icons"]["capsule"],
					style=ButtonStyle.BLURPLE,
					custom_id="capsules",
				),
				Button(
					label=await locale_format(pancakes_loc, pancakes_loc.get("title")),
					emoji=emojis["pancakes"]["normal"],
					style=ButtonStyle.BLURPLE,
					custom_id="pancakes",
				),
				Button(
					label=await locale_format(backgrounds_loc, backgrounds_loc.get("title")),
					emoji=emojis["treasures"]["card"],
					style=ButtonStyle.BLURPLE,
					custom_id="Backgrounds",
				),
				Button(
					label=await locale_format(treasures_loc, treasures_loc.get("buying.title")),
					emoji=emojis["icons"]["inverted_clover"],
					style=ButtonStyle.BLURPLE,
					custom_id="Treasures",
				),
			]
			components = [ActionRow(*buttons)]
		elif category == "capsules":
			nikogotchi: Nikogotchi = await Nikogotchi(ctx.author.id).fetch()
			capsules: dict = (await fetch_item())["capsules"]
			cost = 50_000

			buttons = []

			item = Item(**capsules[-1])
			button = Button(
				label=await locale_format(base_loc, base_loc.get("buttons.buying.single")),
				emoji=PartialEmoji(1147279947086438431),
				style=ButtonStyle.BLURPLE,
				custom_id="nikogotchi_buy",
			)

			if nikogotchi.available or nikogotchi.status > -1:
				button.disabled = True
				button.style = ButtonStyle.RED
				button.label = b_owned

			if wool < item.cost:
				button.disabled = True
				button.style = ButtonStyle.GRAY
				button.label = b_poor

			buttons.append(button)

			buttons.append(go_back)

			title = await locale_format(capsules_loc, capsules_loc.get("title"))
			description = await locale_format(capsules_loc, capsules_loc.get("description"), cost=cost, user_wool=user_wool)

			embeds.append(
				Embed(
					title=title,
					description=description,
					thumbnail=magpie_image,
					color=Colors.SHOP,
				)
			)
			components.append(ActionRow(*buttons))
		elif category == "pancakes":
			pancake_data = await fetch_item()

			nikogotchi_data: Nikogotchi = await Nikogotchi(ctx.author.id).fetch()

			pancake_text_parts = []
			buttons: list[Button] = []
			for id_, pancake in enumerate(pancake_data["pancakes"]):
				pancake = Item(**pancake)
				pancake_id = pancake_id_to_emoji_index_please_rename_them_in_db(pancake.id)
				owned = nikogotchi_data.__getattribute__(pancake.id) or 0

				pancake_loc: dict = await locale_format(items_loc, items_loc.get(f"pancake.{pancake_id}", typecheck=dict))
				pancake_text_parts.append(
					await locale_format(
						pancakes_loc,
						pancakes_loc.get("item_template"),
						pancake_emoji=emojis["pancakes"][pancake_id],
						name=pancake_loc["name"],
						cost=pancake.cost,
						amount_owned=owned,
						description=pancake_loc["description"],
					)
				)
				button = Button(
					label=await locale_format(base_loc, base_loc.get("buttons.buying.single")),
					emoji=emojis["pancakes"][pancake_id],
					style=ButtonStyle.BLURPLE,
					custom_id=f"buy_pancakes_{id_}",
				)

				if wool < pancake.cost:
					button.disabled = True
					button.style = ButtonStyle.GRAY
					button.label = b_poor

				buttons.append(button)

			buttons.append(go_back)

			title = await locale_format(pancakes_loc, pancakes_loc.get("title"))
			description = await locale_format(
				pancakes_loc, pancakes_loc.get("description"), items="\n".join(pancake_text_parts), user_wool=user_wool
			)

			embeds.append(
				Embed(
					title=title,
					description=description,
					thumbnail=magpie_image,
					color=Colors.SHOP,
				)
			)
			components.append(ActionRow(*buttons))
		elif category == "Backgrounds":
			bg_page = kwargs["page"]
			background = daily_shop.background_stock[bg_page]
			all_bgs = await fetch_background()
			fetched_background = all_bgs[background]

			user_backgrounds = user_data.owned_backgrounds

			background_name = await locale_format(items_loc, items_loc.get(f'background["{background}"]'))
			background_description = await locale_format(
				backgrounds_loc,
				backgrounds_loc.get("description"),
				amount=fetched_background["price"],
				user_wool=user_wool,
			)

			embed = Embed(
				title=background_name,
				description=background_description,
				thumbnail=magpie_image,
				color=Colors.SHOP,
			)
			embeds.append(embed)

			embed.set_image(url=fetched_background["image"])

			buttons = [
				Button(
					label="<",
					style=ButtonStyle.BLURPLE,
					custom_id=f"page_prev_{bg_page}",
				),
				Button(
					label=await locale_format(base_loc, base_loc.get("buttons.buying.single")),
					style=ButtonStyle.GREEN,
					custom_id=f"buy_bg_{background}_{bg_page}",
				),
				go_back,
				Button(
					label=">",
					style=ButtonStyle.BLURPLE,
					custom_id=f"page_next_{bg_page}",
				),
			]

			buy_button = buttons[1]

			if wool < fetched_background["price"]:
				buy_button.disabled = True
				buy_button.style = ButtonStyle.GRAY
				buy_button.label = b_poor

			if background in user_backgrounds:
				embed.description = None
				buy_button.disabled = True
				buy_button.style = ButtonStyle.RED
				buy_button.label = b_owned

			buttons[1] = buy_button
			components.append(ActionRow(*buttons))
		elif category == "Treasures":
			stock: str = await locale_format(
				treasures_loc,
				treasures_loc.get("stock_market"),
				change=daily_shop.stock.value,
				rate=daily_shop.stock.price,
			)
			selected_treasure = kwargs.get("selected_treasure", None)
			selected_treasure_loc: dict = {"name": "???"}
			buy_price_one = 0
			buy_price_all = 0

			treasure_details = ""

			user_data = await UserData(_id=ctx.author.id).fetch()

			owned = user_data.owned_treasures
			all_treasures = await fetch_treasure()

			if selected_treasure is not None:
				get_selected_treasure = all_treasures[selected_treasure]
				selected_treasure_loc: dict = await locale_format(
					items_loc, items_loc.get(f"treasure.{selected_treasure}", typecheck=dict)
				)

				amount_owned = owned.get(selected_treasure, 0)

				buy_price_one = int(get_selected_treasure["price"] * daily_shop.stock.price)

				current_balance = user_data.wool

				max_allowed = max(1, min(self.max_buy_sell_limit, self.max_wool_limit // max(1, buy_price_one)))
				affordable = current_balance // max(1, buy_price_one)

				amount = min(max_allowed, affordable)
				buy_price_all = int(amount * buy_price_one)

				limit_reached = "yes" if affordable > max_allowed else None

				treasure_details = await locale_format(
					treasures_loc,
					treasures_loc.get("selection"),
					treasure_icon=emojis["treasures"][selected_treasure],
					treasure_name=selected_treasure_loc["name"],
					owned_count=amount_owned,
					amount_selected=amount_owned,
					price_one=buy_price_one,
					price_all=buy_price_all,
					amount=amount,
					limit_reached=limit_reached,
				)

			treasure_stock: list[TreasureTypes] = daily_shop.treasure_stock

			buttons: list[Button] = []

			user_data = await UserData(_id=ctx.author.id).fetch()

			owned = user_data.owned_treasures

			treasure_list = []
			for treasure in treasure_stock:
				get_treasure = all_treasures[treasure]

				treasure_loc: dict = await locale_format(items_loc, items_loc.get(f"treasure.{treasure}", typecheck=dict))

				treasure_list.append(
					StringSelectOption(
						label=await locale_format(
							treasures_loc,
							treasures_loc.get("buying.select_menu.option"),
							name=treasure_loc["name"],
							price=get_treasure["price"],
						),
						description=treasure_loc["description"],
						value=treasure,
						emoji=emojis["treasures"][treasure],
					)
				)

			if selected_treasure is not None:
				get_selected_treasure = all_treasures[selected_treasure]

				button = Button(
					label=await locale_format(base_loc, base_loc.get("buttons.buying.single")),
					emoji=emojis["treasures"][selected_treasure],
					style=ButtonStyle.BLURPLE,
					custom_id=f"treasure_buy_{selected_treasure}_One",
				)

				button_all = Button(
					label=await locale_format(
						base_loc, base_loc.get("buttons.buying.multiple"), amount=amount, limit_reached=limit_reached
					),
					emoji=emojis["treasures"][selected_treasure],
					style=ButtonStyle.BLURPLE,
					custom_id=f"treasure_buy_{selected_treasure}_All",
				)

				if wool < buy_price_one:
					button.disabled = True
					button.style = ButtonStyle.GRAY
					button.label = b_poor

					button_all.disabled = True
					button_all.style = ButtonStyle.GRAY
					button_all.label = b_poor

				buttons.append(button)
				buttons.append(button_all)

			buttons.append(
				Button(
					label=await locale_format(treasures_loc, treasures_loc.get("selling.title")),
					style=ButtonStyle.GREEN,
					custom_id="sell_treasure_menu",
				)
			)

			buttons.append(go_back)

			title = await locale_format(treasures_loc, treasures_loc.get("buying.title"))
			description = await locale_format(
				treasures_loc,
				treasures_loc.get("buying.description"),
				stock_market=stock,
				selected_treasure=treasure_details,
				user_wool=user_wool,
			)

			embeds.append(
				Embed(
					title=title,
					description=description,
					thumbnail=magpie_image,
					color=Colors.SHOP,
				)
			)

			select_menu = None

			if len(treasure_list) > 0:
				select_menu = StringSelectMenu(
					*treasure_list,
					placeholder=await locale_format(treasures_loc, treasures_loc.get("buying.select_menu.placeholder")),
					custom_id="select_treasure",
				)
			else:
				select_menu = StringSelectMenu(
					"💥💥💥💥💥💥💥💥💥💥💥💥",
					placeholder=await locale_format(treasures_loc, treasures_loc.get("buying.select_menu.no_treasures")),
					custom_id="select_treasure",
					disabled=True,
				)

			components = [ActionRow(select_menu), ActionRow(*buttons)]
		elif category == "Sell_Treasures":
			stock: str = await locale_format(
				treasures_loc,
				treasures_loc.get("stock_market"),
				change=daily_shop.stock.value,
				rate=daily_shop.stock.price,
			)

			go_back = Button(
				label=await locale_format(base_loc, base_loc.get("buttons.go_back")),
				style=ButtonStyle.GRAY,
				custom_id="Treasures",
			)
			selected_treasure = kwargs.get("selected_treasure", None)
			selected_treasure_loc: dict = {"name": "???"}
			sell_price_one = 0
			sell_price_all = 0

			treasure_details = ""

			user_data = await UserData(_id=ctx.author.id).fetch()

			owned = user_data.owned_treasures
			all_treasures = await fetch_treasure()

			if selected_treasure is not None:
				get_selected_treasure = all_treasures[selected_treasure]
				selected_treasure_loc: dict = await locale_format(
					items_loc, items_loc.get(f"treasure.{selected_treasure}", typecheck=dict)
				)

				sell_price_one = int(get_selected_treasure["price"] * daily_shop.stock.price)
				amount_owned = int(owned.get(selected_treasure, 0))

				max_allowed = max(1, min(self.max_buy_sell_limit, self.max_wool_limit // max(1, sell_price_one)))
				amount_selected = min(amount_owned, max_allowed)
				sell_price_all = amount_selected * sell_price_one

				limit_reached = "yes" if amount_owned > max_allowed else None

				if amount_owned > 0:
					treasure_details = await locale_format(
						treasures_loc,
						treasures_loc.get("selection"),
						treasure_icon=emojis["treasures"][selected_treasure],
						treasure_name=selected_treasure_loc["name"],
						owned_count=amount_owned,
						amount_selected=amount_owned,
						price_one=sell_price_one,
						price_all=sell_price_all,
						amount=amount_selected,
						limit_reached=limit_reached,
					)

			treasure_selection = []

			for key, amount in owned.items():
				if key not in get_args(TreasureTypes):
					raise ValueError(f"Unknown treasure type: {key}")
				treasure_id: TreasureTypes = key  # type:ignore

				if amount <= 0:
					continue

				treasure_loc = await locale_format(items_loc, items_loc.get(f"treasure.{treasure_id}", typecheck=dict))

				treasure_selection.append(
					StringSelectOption(
						label=await locale_format(
							treasures_loc,
							treasures_loc.get("selling.select_menu.option"),
							name=treasure_loc["name"],
							amount=amount,
						),
						value=treasure_id,
						description=treasure_loc["description"],
						emoji=emojis["treasures"][treasure_id],
					)
				)

			buttons = []

			if selected_treasure is not None:
				treasure_id = selected_treasure

				buttons = [
					Button(
						label=await locale_format(base_loc, base_loc.get("buttons.selling.single")),
						custom_id=f"treasure_sell_{treasure_id}_one",
						style=ButtonStyle.GREEN,
					),
					Button(
						label=await locale_format(
							base_loc,
							base_loc.get("buttons.selling.multiple"),
							amount=amount_selected,
							limit_reached=limit_reached,
						),
						custom_id=f"treasure_sell_{treasure_id}_all",
						style=ButtonStyle.GREEN,
					),
				]

			buttons.append(go_back)

			embeds.append(
				Embed(
					title=await locale_format(treasures_loc, treasures_loc.get("selling.title")),
					description=await locale_format(
						treasures_loc,
						treasures_loc.get("selling.description"),
						stock_market=stock,
						selected_treasure=treasure_details,
						user_wool=user_wool,
					),
					thumbnail=magpie_image,
					color=Colors.SHOP,
				)
			)

			select_menu = None

			if len(treasure_selection) > 0:
				select_menu = StringSelectMenu(
					*treasure_selection,
					placeholder=await locale_format(treasures_loc, treasures_loc.get("selling.select_menu.placeholder")),
					custom_id="select_treasure_sell",
				)
			else:
				select_menu = StringSelectMenu(
					"💥💥💥💥💥💥💥💥💥💥💥💥",
					placeholder=await locale_format(treasures_loc, treasures_loc.get("selling.select_menu.no_treasures")),
					custom_id="select_treasure_sell",
					disabled=True,
				)

			components = [ActionRow(select_menu), ActionRow(*buttons)]

		return (embeds, components)

	@slash_command(description="Open Magpie's Shop")
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def shop(self, ctx: SlashContext):
		await ctx.defer(ephemeral=True)
		loc = Localization(ctx, prefix="commands.shop.base")
		loading = asyncio.create_task(fancy_message(ctx, await locale_format(loc, loc.get("loading"))))

		await self.get_shop()

		embeds, button = await self.embed_manager(ctx, "main_shop")

		await loading
		await ctx.edit(embeds=embeds, components=button)
