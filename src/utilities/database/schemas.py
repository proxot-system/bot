import logging
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime

from utilities.database.main import Collection, DBDict, DBDynamicDict, DBList
from utilities.emojis import TreasureTypes
from utilities.logging import createLogger


class TransmitConfig(DBDict):
	disabled: bool = False
	channel_id: str | None = None
	anonymous: bool = False
	allow_images: bool = True
	blocked_servers: DBList[str] = field(default_factory=lambda: DBList())
	known_servers: DBList[str] = field(default_factory=lambda: DBList())


class WelcomeConfig(DBDict):
	disabled: bool = True
	ping: bool = False
	channel_id: str | None = None
	# character: str = None
	# face: str = None
	# animated: bool = True
	message: str = ""
	errored: bool = False


@dataclass
class ServerData(Collection):
	transmissions: TransmitConfig = field(default_factory=TransmitConfig)
	welcome: WelcomeConfig = field(default_factory=WelcomeConfig)

databaseLogger = createLogger("database")
@dataclass
class UserData(Collection):
	minis_shown: DBDynamicDict[str, int] = field(default_factory=lambda: DBDynamicDict())
	wool: int = 0
	suns: int = 0
	equipped_bg: str = "Default"
	profile_description: str = "Hello World!"
	badge_notifications: bool = True
	owned_treasures: DBDynamicDict[TreasureTypes, int] = field(default_factory=lambda: DBDynamicDict({"journal": 5}))
	owned_backgrounds: DBList[str] = field(
		default_factory=lambda: DBList(["Default", "Blue", "Red", "Yellow", "Green", "Pink"])
	)
	owned_badges: DBList[str] = field(default_factory=lambda: DBList())
	gamble_queue: DBList[int] = field(default_factory=lambda: DBList())
	ask_limit: int = 14
	last_asked: datetime = field(default_factory=lambda: datetime(2000, 1, 1, 0, 0, 0))
	daily_wool_timestamp: datetime = field(default_factory=lambda: datetime(2000, 1, 1, 0, 0, 0))
	daily_sun_timestamp: datetime = field(default_factory=lambda: datetime(2000, 1, 1, 0, 0, 0))
	times_asked: int = 0
	times_transmitted: int = 0
	times_shattered: int = 0
	translation_language: str = "english"

	async def manage_wool(self, amount: int):
		databaseLogger.log(logging.DEBUG, f"{'took' if amount < 0 else 'gave'} user {self._id}, {amount} wool")
		wool = self.wool + amount

		if wool <= 0:
			wool = 0
		elif wool >= 999_999_999_999_999_999:
			wool = 999_999_999_999_999_999

		return await self.update(wool=int(wool))


@dataclass
class StatUpdate:
	icon: str
	old_value: int
	new_value: int


@dataclass
class Nikogotchi(Collection):
	available: bool = False
	hatched: datetime = field(default_factory=lambda: datetime.now())
	last_interacted: datetime = field(default_factory=lambda: datetime.now())
	started_finding_treasure_at: datetime = field(default_factory=lambda: datetime.now())
	status: int = -1

	rarity: int = 0
	pancakes: int = 5
	golden_pancakes: int = 1
	glitched_pancakes: int = 0

	level: int = 0
	health: int = 50
	energy: int = 5
	hunger: int = 50
	cleanliness: int = 50
	happiness: int = 50

	attack: int = 5
	defense: int = 2

	max_health: int = 50
	max_hunger: int = 50
	max_cleanliness: int = 50
	max_happiness: int = 50

	nid: str = "?"
	name: str = "NONAME"
	pronouns: str = "it/its"

	async def level_up(self, amount: int) -> list[StatUpdate]:
		level = self.level + amount

		stats: list[StatUpdate] = []

		algorithm = int(amount * 5 * random.uniform(0.8, 1.4))
		stats.append(StatUpdate("❤️", int(self.max_health), int(self.max_health) + int(algorithm)))
		self.max_health += algorithm

		algorithm = int(amount * 5 * random.uniform(0.8, 1.4))
		stats.append(StatUpdate("🍴", int(self.max_hunger), int(self.max_hunger) + int(algorithm)))
		self.max_hunger += algorithm

		algorithm = int(amount * 5 * random.uniform(0.8, 1.4))
		stats.append(
			StatUpdate(
				"🫂",
				int(self.max_happiness),
				int(self.max_happiness) + int(algorithm),
			)
		)
		self.max_happiness += algorithm

		algorithm = int(amount * 5 * random.uniform(0.8, 1.4))
		stats.append(
			StatUpdate(
				"🧽",
				int(self.max_cleanliness),
				int(self.max_cleanliness) + int(algorithm),
			)
		)
		self.max_cleanliness += algorithm

		algorithm = int(amount * 2 * random.uniform(0.8, 1.4))
		stats.append(StatUpdate("🗡️", int(self.attack), int(self.attack) + int(algorithm)))
		self.attack += algorithm

		algorithm = int(amount * 2 * random.uniform(0.8, 1.4))
		stats.append(StatUpdate("🛡️", int(self.defense), int(self.defense) + int(algorithm)))
		self.defense += algorithm

		self.level = level

		self.health = self.max_health
		self.hunger = self.max_hunger
		self.happiness = self.max_happiness
		self.cleanliness = self.max_cleanliness

		await self.update(**asdict(self))

		return stats