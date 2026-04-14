from typing import Union

from interactions import Snowflake


class Connection:
	def __init__(self, server_id, channel_id):
		self.server_id = server_id
		self.channel_id = channel_id
		self.characters = [  # TODO: import from textbox characters
			{"id": 0, "Image": 1019605517695463484, "Name": "Niko"},
			{"id": 0, "Image": 1071085652327813212, "Name": "Alula"},
			{"id": 0, "Image": 1071085682132529294, "Name": "Calamus"},
			{"id": 0, "Image": 1071085718975283310, "Name": "Lamplighter"},
			{"id": 0, "Image": 1027240024992927814, "Name": "Kip"},
			{"id": 0, "Image": 1090982149659836466, "Name": "Ling"},
			{"id": 0, "Image": 1023573456664662066, "Name": "The World Machine"},
		]


class Transmission:
	def __init__(self, a: Connection, b: Union[Connection, None]):
		self.connection_a = a
		self.connection_b = b


transmissions: list[Transmission] = []


def create_connection(server_id: Snowflake, channel_id: Snowflake) -> Transmission:
	conn = Connection(server_id, channel_id)
	trans = Transmission(conn, None)
	transmissions.append(trans)
	return trans


def remove_connection(server_id: Snowflake | Transmission):
	trans = get_transmission(server_id)
	if trans is None:
		return
	trans.connection_b = None

	if trans in transmissions:
		transmissions.remove(trans)


def connect_to_transmission(server_id, channel_id):
	for transmission in transmissions:
		if transmission.connection_b is None:
			transmission.connection_b = Connection(server_id, channel_id)
			return


def get_transmission(server_id: Snowflake | Transmission) -> Transmission | None:
	if isinstance(server_id, Transmission):
		return server_id
	for transmission in transmissions:
		for connection in [transmission.connection_a, transmission.connection_b]:
			if connection and connection.server_id == server_id:
				return transmission


def connection_alive(transmission: Snowflake | Transmission) -> bool:
	trans = get_transmission(transmission)
	if trans is None:
		return False
	if trans.connection_b is None:
		return False
	return True


def attempting_to_connect(server_id: Snowflake | Transmission) -> bool:
	trans = get_transmission(server_id)
	if trans is None:
		return False
	return trans.connection_b is None


def available_initial_connections(block_list) -> bool:
	for transmission in transmissions:
		if transmission.connection_b is None:
			if transmission.connection_a.server_id in block_list:
				continue

			return False

	return True


def check_if_connected(server_id: Snowflake | Transmission) -> bool:
	trans = get_transmission(server_id)
	if trans is None:
		return False
	if trans.connection_b is None:
		return False
	elif trans.connection_b.server_id == server_id:
		return True

	return False
