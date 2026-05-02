import urllib.parse
from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Generic, Iterable, MutableMapping, TypeVar, get_origin, get_type_hints, overload

import yaml
from interactions import Snowflake
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi

from utilities.config import get_config

if get_config("database.dnsFix", typecheck=bool, ignore_None=True):
	import dns.resolver

	dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
	dns.resolver.default_resolver.nameservers = ["8.8.8.8"]


def init_things(self):
	type_hints = get_type_hints(self.__class__)
	if is_dataclass(self):
		for field_info in fields(self):
			value = getattr(self, field_info.name)
			name = field_info.name

			field_type = type_hints.get(name)
			assert field_type is not None

			if name in ["_id", "_parent", "_parent_field"]:
				continue

			if isinstance(value, dict):
				if get_origin(field_type) == DBDynamicDict:
					setattr(self, name, field_type(_parent=self, _parent_field=name, **value))
				else:
					setattr(self, name, init_things(field_type(_parent=self, _parent_field=name, **value)))
			elif isinstance(value, list):
				setattr(self, name, field_type(default=value, _parent=self, _parent_field=name))
	return self


TCollection = TypeVar("TCollection", bound="Collection")


@dataclass
class Collection:
	_id: str | Snowflake

	async def update(self, **kwargs):
		"""Update the current collection with the given kwargs."""
		updated_data = await update_in_database(self, **kwargs)
		# The new overloads for to_dict will correctly infer a dict type here
		for k, v in to_dict(updated_data).items():
			setattr(self, k, v)
		return init_things(updated_data)

	async def fetch(self: TCollection) -> TCollection:
		"""Fetch the current collection using id."""
		self._id = str(self._id)

		db = await get_database()

		result = await db.get_collection(self.__class__.__name__).find_one({"_id": str(self._id)})

		if result is None:
			await new_entry(self)
			return await self.fetch()
		return self.__class__(**result)

	def __post_init__(self):
		init_things(self)

	async def update_array(self, field: str, operator: str, value: Any):
		db = await get_database()
		await db.get_collection(self.__class__.__name__).update_one({"_id": str(self._id)}, {operator: {field: value}})

	async def increment_key(self, key: str, by: int | float = 1):
		value = getattr(self, key, 0)

		if isinstance(value, float):
			by = float(by)
		# could use self.key += by maybe, instead of returning a whole new objec (.update does that)
		return await self.update(**{key: value + by})


class DBDict(MutableMapping):
	_parent: Collection | None
	_parent_field: str | None

	def __init__(self, *args, _parent: "Collection | None" = None, _parent_field: str | None = None, **kwargs):
		self._parent = _parent
		self._parent_field = _parent_field

		from dataclasses import MISSING, Field
		from typing import get_origin, get_type_hints

		try:
			type_hints = get_type_hints(self.__class__)
		except Exception:
			type_hints = {}

		initial_data = dict(*args, **kwargs)

		for key, expected_type in type_hints.items():
			if key.startswith("_"):
				continue
			if key not in initial_data and hasattr(self.__class__, key):
				default_val = getattr(self.__class__, key)
				if isinstance(default_val, Field):
					if default_val.default_factory is not MISSING:
						initial_data[key] = default_val.default_factory()
					elif default_val.default is not MISSING:
						initial_data[key] = default_val.default
				else:
					initial_data[key] = default_val

		for key, value in initial_data.items():
			expected_type = type_hints.get(key)
			if expected_type is not None:
				origin = get_origin(expected_type) or expected_type
				if isinstance(value, list) and isinstance(origin, type) and issubclass(origin, list):
					value = origin(default=value, _parent=self, _parent_field=key)  # type:ignore
				elif isinstance(value, dict) and isinstance(origin, type) and issubclass(origin, DBDict):
					value = origin(_parent=self, _parent_field=key, **value)  # type:ignore

			setattr(self, key, value)

	def __setitem__(self, key, value):
		setattr(self, key, value)

	def __getitem__(self, key):
		try:
			return getattr(self, key)
		except AttributeError:
			raise KeyError(key)

	def __delitem__(self, key):
		try:
			delattr(self, key)
		except AttributeError:
			raise KeyError(key)

	def __iter__(self):
		return (key for key in self.__dict__ if not key.startswith("_"))

	def __len__(self):
		return len(list(self.__iter__()))

	def __repr__(self):
		contents = {k: v for k, v in self.items()}
		return f"DB{repr(contents)}"

	async def sync_to_db(self):
		"""Helper method to sync the entire current state to the database."""
		if self._parent is None or self._parent_field is None:
			raise Exception("Parent not set for nested update.")

		update_fields = {self._parent_field: to_dict(self)}
		await self._parent.update(**update_fields)

	async def update(self, *args, **kwargs):
		"""Updates local attributes and then syncs the entire object to the database."""
		update_data = dict(*args, **kwargs)
		for key, value in update_data.items():
			self[key] = value

		await self.sync_to_db()

	async def increment_key(self, key: str, by: int | float = 1):
		value = self.get(key, 0)
		if isinstance(value, float):
			by = float(by)

		self[key] = value + by

		await self.sync_to_db()

	async def update_array(self, field: str, operator: str, value: Any):
		if self._parent is None or self._parent_field is None:
			raise Exception("Parent not set for nested update.")
		await self._parent.update_array(f"{self._parent_field}.{field}", operator, value)

	async def fetch(self) -> "Collection":
		if self._parent is None or self._parent_field is None:
			raise Exception("Parent not set for nested fetch.")
		parent_data = await self._parent.fetch()
		return getattr(parent_data, self._parent_field)


TItem = TypeVar("TItem")


class DBList(list, Generic[TItem]):
	_parent: Collection | None
	_parent_field: str | None

	def __init__(
		self,
		default: Iterable[TItem] | None = None,
		_parent: Collection | None = None,
		_parent_field: str | None = None,
	):
		super().__init__(default or [])

		self._parent = _parent
		self._parent_field = _parent_field

	def __repr__(self):
		return f"DB{super().__repr__()}"

	async def append(self, item: TItem) -> None:
		"""Append object to the end of the list, and update self in the database"""
		if self._parent is None or self._parent_field is None:
			raise Exception("Parent not set for nested update.")

		await self._parent.update_array(self._parent_field, "$push", item)
		super().append(item)

	async def remove(self, item: TItem) -> None:
		"""Remove first occurrence of value, and update self in the database"""
		if self._parent is None or self._parent_field is None:
			raise Exception("Parent not set for nested update.")

		await self._parent.update_array(self._parent_field, "$pull", item)
		super().remove(item)

	async def extend(self, iterable: Iterable[TItem]) -> None:
		"""Extend the list by appending items from the iterable, and update self in the database"""
		if self._parent is None or self._parent_field is None:
			raise Exception("Parent not set for nested update.")

		items_to_add = list(iterable)
		if not items_to_add:
			return

		# MongoDB's $push with $each expects a list of items
		await self._parent.update_array(self._parent_field, "$push", {"$each": items_to_add})
		super().extend(items_to_add)

	async def clear(self) -> None:
		"""Clear the list, and update self in the database"""
		if self._parent is None or self._parent_field is None:
			raise Exception("Parent not set for nested update.")

		await self._parent.update_array(self._parent_field, "$set", [])
		super().clear()


TKey = TypeVar("TKey")
TValue = TypeVar("TValue")


class DBDynamicDict(MutableMapping, Generic[TKey, TValue]):
	_parent: Collection | None
	_parent_field: str | None

	def __init__(self, *args: Any, _parent: Collection | None = None, _parent_field: str | None = None, **kwargs: Any):
		self._parent = _parent
		self._parent_field = _parent_field

		initial_data = dict(*args, **kwargs)
		for key, value in initial_data.items():
			setattr(self, str(key), value)

	def __setitem__(self, key: TKey, value: TValue) -> None:
		setattr(self, str(key), value)

	def __getitem__(self, key: TKey) -> TValue:
		try:
			return getattr(self, str(key))
		except AttributeError:
			raise KeyError(key)

	def __delitem__(self, key: TKey) -> None:
		try:
			delattr(self, str(key))
		except AttributeError:
			raise KeyError(key)

	def __iter__(self) -> TKey:
		return (key for key in self.__dict__ if not key.startswith("_"))  # type: ignore

	def __len__(self) -> int:
		return len(list(self.__iter__()))  # type: ignore

	def __repr__(self) -> str:
		contents = {k: v for k, v in self.items()}
		return f"DBD{repr(contents)}"

	async def sync_to_db(self):
		"""Helper method to sync the entire current state to the database."""
		if self._parent is None or self._parent_field is None:
			raise Exception("Parent not set for nested update.")

		update_fields = {self._parent_field: to_dict(self)}
		await self._parent.update(**update_fields)

	async def set_and_sync(self, key: TKey, value: TValue):
		"""Sets a key/value pair locally and then syncs to the database."""
		self[key] = value

		await self.sync_to_db()

	async def update(self, *args: Any, **kwargs: Any) -> None:
		"""Updates from another dictionary or kwargs and syncs to the database."""
		update_data = dict(*args, **kwargs)
		for key, value in update_data.items():
			self[key] = value  # type: ignore

		await self.sync_to_db()

	async def increment_key(self, key: TKey, by: int | float = 1) -> None:
		current_value = self.get(key, 0)

		if not isinstance(current_value, (int, float)):
			current_value = 0

		await self.set_and_sync(key, (current_value + by))  # type: ignore


connection = None


async def connect_to_db():
	global connection
	if connection is not None:
		return

	# Helper logic to dynamically build the URI to avoid shell parsing issues
	username = urllib.parse.quote_plus(get_config("database.connection.username"))
	password = urllib.parse.quote_plus(get_config("database.connection.password"))
	host = get_config("database.connection.host")
	port = get_config("database.connection.port")

	connection_uri = f"mongodb://{username}:{password}@{host}:{port}/?authSource=admin"

	connection = AsyncIOMotorClient(connection_uri, server_api=ServerApi("1"))
	try:
		await connection.admin.command("ping")
		print("Database Connected")
	except Exception as e:
		print(f"Failed to connect to database: {e}")


async def get_database():
	if connection is None:
		await connect_to_db()
	assert connection is not None

	return connection.get_database("TheWorldMachine")


async def new_entry(collection: Collection):
	db = await get_database()

	await db.get_collection(collection.__class__.__name__).update_one(
		{"_id": str(collection._id)}, {"$set": to_dict(collection)}, upsert=True
	)


async def update_in_database(collection: TCollection, **kwargs) -> TCollection:
	db = await get_database()
	existing_data = to_dict(collection)
	updated_data = {**existing_data, **kwargs}  # pyright: ignore[reportGeneralTypeIssues]
	await db.get_collection(collection.__class__.__name__).update_one(
		{"_id": str(collection._id)}, {"$set": updated_data}, upsert=True
	)
	return collection.__class__(**updated_data)


async def fetch_items():
	db = await get_database()

	data = await db.get_collection("ItemData").find_one({"access": "ItemData"})

	return data


async def update_shop(data: dict):
	db = await get_database()

	await db.get_collection("ItemData").update_one({"access": "ItemData"}, {"$set": {"shop": data}})


Serializable = (
	dict[str, "Serializable"] | list["Serializable"] | tuple["Serializable", ...] | str | int | float | bool | None
)

T_Primitive = TypeVar("T_Primitive", str, int, float, bool)


@overload
def to_dict(obj: "Collection") -> dict[str, Serializable]: ...


@overload
def to_dict(obj: DBDict) -> dict[str, Serializable]: ...


@overload
def to_dict(obj: DBDynamicDict) -> dict[str, Serializable]: ...


@overload
def to_dict(obj: dict[Any, Any]) -> dict[str, Serializable]: ...


@overload
def to_dict(obj: DBList) -> list[Serializable]: ...


@overload
def to_dict(obj: list[Any]) -> list[Serializable]: ...


@overload
def to_dict(obj: tuple[Any, ...]) -> tuple[Serializable, ...]: ...


@overload
def to_dict(obj: T_Primitive) -> T_Primitive: ...


@overload
def to_dict(obj: None) -> None: ...


def to_dict(obj: Any) -> Serializable:
	"""
	Recursively converts a Python object into a serializable dictionary.
	"""
	if is_dataclass(obj):
		result: dict[str, Serializable] = {}
		for f in fields(obj):
			if f.name in ["_parent", "_parent_field", "_field_name"]:
				continue
			value = getattr(obj, f.name)
			result[f.name] = to_dict(value)
		return result
	elif isinstance(obj, (DBList, list)):
		return [to_dict(x) for x in obj]
	elif isinstance(obj, tuple):
		return tuple(to_dict(x) for x in obj)
	elif isinstance(obj, (DBDict, DBDynamicDict, dict)):
		return {str(k): to_dict(v) for k, v in obj.items()}
	else:
		return obj


for dc in (yaml.Dumper, yaml.SafeDumper):
	yaml.add_representer(DBList, lambda dumper, data: dumper.represent_list(list(data)), Dumper=dc)
	yaml.add_representer(DBDict, lambda dumper, data: dumper.represent_dict(to_dict(data)), Dumper=dc)
	yaml.add_representer(
		DBDynamicDict,
		lambda dumper, data: dumper.represent_dict(to_dict(data)),
		Dumper=dc,
	)
