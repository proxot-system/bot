import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from utilities.database.main import fetch_items, update_shop
from utilities.emojis import TreasureTypes
from utilities.localization.localization import source_loc


@dataclass
class DictItem:
	nid: str
	cost: int
	image: str
	type: int


@dataclass
class Item:
	cost: int
	image: int
	id: Literal["pancakes", "golden_pancakes", "glitched_pancakes"]


@dataclass
class StockData:
	price: float
	value: float


@dataclass
class ShopData:
	last_updated: datetime
	background_stock: list[str]
	treasure_stock: list[TreasureTypes]
	stock: StockData
	motd: int


async def fetch_shop_data():
	items = await fetch_items()
	assert items is not None

	shop_data = ShopData(
		last_updated=items["shop"]["last_updated"],
		background_stock=items["shop"]["backgrounds"],
		treasure_stock=items["shop"]["treasures"],
		stock=StockData(items["shop"]["stock"]["price"], items["shop"]["stock"]["value"]),
		motd=items["shop"]["motd"],
	)

	return shop_data


async def get_shop_data():
	data = await fetch_shop_data()

	if (data.last_updated + timedelta(days=1)) > datetime.now():
		return data

	items = await fetch_items()
	assert items is not None

	all_bgs = items["backgrounds"]
	backgrounds = {bg: val for bg, val in all_bgs.items() if val["purchasable"]}
	treasures = items["treasures"]
	motds = source_loc.get("shop.motds", typecheck=tuple)

	data.background_stock = random.sample(list(backgrounds.keys()), 3)
	data.treasure_stock = random.sample(list(treasures.keys()), 3)
	data.motd = random.randint(0, len(motds) - 1)

	now = datetime.now()
	data.last_updated = datetime(now.year, now.month, now.day, hour=0, minute=0, second=0)

	is_positive = random.choice([True, False])

	if data.stock.price < 0.5:
		is_positive = True
	elif data.stock.price > 1.5:
		is_positive = False

	if is_positive:
		data.stock.value = round(random.uniform(0.05, 0.2), 1)
	else:
		data.stock.value = round(random.uniform(-0.2, -0.05), 1)

	price_change = data.stock.price + data.stock.value
	data.stock.price = round(min(2, max(0.2, price_change)), 1)

	await update_shop(
		{
			"last_updated": data.last_updated,
			"backgrounds": data.background_stock,
			"treasures": data.treasure_stock,
			"motd": data.motd,
			"stock": {"price": data.stock.price, "value": data.stock.value},
		}
	)

	return data
