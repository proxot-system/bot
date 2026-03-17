import asyncio
import uuid
from typing import Literal

# ruff: noqa: ERA001
from interactions import (
	TYPE_ALL_CHANNEL,
	TYPE_MESSAGEABLE_CHANNEL,
	Button,
	ButtonStyle,
	ChannelType,
	Embed,
	Extension,
	Guild,
	Member,
	Message,
	SlashContext,
	User,
	contexts,
	integration_types,
	listen,
	slash_command,
)
from interactions.api.events import Component, MessageCreate

from utilities.database.schemas import ServerData
from utilities.emojis import emojis
from utilities.localization.formatting import ftime
from utilities.message_decorations import Colors, fancy_message
from utilities.profile.badge_manager import increment_value
from utilities.transmission_connection_manager import (
	Connection,
	Transmission,
	available_initial_connections,
	connect_to_transmission,
	connection_alive,
	create_connection,
	get_transmission,
	remove_connection,
)


class TransmissionCommands(Extension):
	@slash_command(description="Transmit to other servers!")
	@integration_types(guild=True, user=False)
	@contexts(bot_dm=False)
	async def transmit(self, ctx: SlashContext):
		pass

	#
	# @transmit.subcommand(sub_cmd_description='Connect to a server you already know.')
	# async def call(self, ctx: SlashContext):

	# 	server_data: ServerData = await ServerData(_id=ctx.guild.id).fetch()

	# 	guilds = [
	# 		await ctx.client.fetch_guild(id) or id
	# 		for id in list(set(server_data.transmissions.known_servers + server_data.transmissions.blocked_servers))
	# 	]
	#
	# 	server_ids = {
	# 		guild.id if isinstance(guild, Guild) else guild
	# 		:
	# 									guild.name if isinstance(guild, Guild) else (await lformat(loc, loc.l("transmit.autocomplete.unknown_server"), server_id=guild), True)
	# 		for guild in guilds
	# 	}

	# 	if attempting_to_connect(ctx.guild.id):
	# 		return await fancy_message(ctx, '[ This server is already transmitting! ]', ephemeral=True)

	# 	if server_data.transmissions.disabled:
	# 		return await fancy_message(ctx,
	# 								   '[ This server has opted to disable call transmissions or has simply not set a channel. ]',
	# 								   ephemeral=True)

	# 	if not server_ids:
	# 		return await fancy_message(ctx,
	# 								   '[ This server hasn't connected to anyone before! Connect using ``/transmit connect``! ]',
	# 								   ephemeral=True)

	# 	options = []

	# 	server_name = ''

	# 	for server_id, name in server_ids.items():
	# 		options.append(
	# 			StringSelectOption(
	# 				label=name,
	# 				value=server_id
	# 			)
	# 		)

	# 	server_list = StringSelectMenu(
	# 		options,
	# 		custom_id=str(ctx.guild.id),
	# 		placeholder='Connect to...',
	# 	)

	# 	await ctx.send(components=server_list, ephemeral=True)

	# 	select_results = await ctx.client.wait_for_component(components=server_list)

	# 	other_server = int(select_results.ctx.values[0])
	# 	other_server_data: ServerData = await ServerData(_id=other_server).fetch()

	# 	if other_server in server_data.transmissions.blocked_servers:
	# 		return await fancy_message(select_results.ctx, '[ Sorry, but this server is blocked. ]', color=Colors.BAD, ephemeral=True)

	# 	if ctx.guild_id in other_server_data.transmissions.blocked_servers:
	# 		return await fancy_message(select_results.ctx, '[ Sorry, but this server has blocked you. ]', color=Colors.BAD, ephemeral=True)

	# 	if not other_server_data.transmissions.channel_id:
	# 		return await fancy_message(select_results.ctx,
	# 								   '[ Sorry, but the server you selected has not set a channel for transmissions yet. ]',
	# 								   color=Colors.BAD, ephemeral=True)

	# 	other_server_channel: GuildText = await ctx.client.fetch_channel(other_server_data.transmissions.channel_id)

	# 	server_name = other_server_channel.guild.name.replace("`", "'")

	# 	connect_button = Button(
	# 		style=ButtonStyle.PRIMARY,
	# 		label='Answer',
	# 		custom_id='answer_phone'
	# 	)

	# 	disconnect_button = Button(
	# 		style=ButtonStyle.DANGER,
	# 		label='Decline',
	# 		custom_id='decline_phone'
	# 	)

	# 	embed_one = Embed(
	# 		description=f"``[ Calling **{server_name}**... ``{emojis['icons']['loading']}` ]`",
	# 		color=Colors.DARKER_WHITE
	# 	)

	# 	embed_timeout_one = Embed(
	# 		description='``[ Sorry! You took too long to respond! ]``',
	# 		color=Colors.RED
	# 	)
	# 	embed_timeout_two = Embed(
	# 		description='``[ Sorry! The other server took too long to respond! ]``',
	# 		color=Colors.RED
	# 	)

	# 	embed_cancel_one = Embed(
	# 		description='``[ Successfully Declined. ]``',
	# 		color=Colors.WARN
	# 	)
	# 	embed_cancel_two = Embed(
	# 		description='``[ Sorry! The other server declined the call! ]``',
	# 		color=Colors.RED
	# 	)

	# 	message = await select_results.ctx.send(embed=embed_one)

	# 	other_server_message = await fancy_message(other_server_channel, f'[ **{ctx.guild.name}** is calling you! ]', components=[connect_button, disconnect_button])

	# 	try:
	# 		other_server_component: Component = await ctx.client.wait_for_component(components=[connect_button, disconnect_button], timeout=60)
	# 	except:

	# 		await other_server_message.edit(embed=embed_timeout_one, components=[])
	# 		await message.edit(embed=embed_timeout_two)
	# 		return

	# 	other_server_ctx = other_server_component.ctx

	# 	await other_server_ctx.defer(edit_origin=True)

	# 	button_id = other_server_ctx.custom_id

	# 	if button_id == 'decline_phone':

	# 		await other_server_message.edit(embed=embed_cancel_one, components=[])
	# 		await message.edit(embed=embed_cancel_two)
	# 	else:

	# 		create_connection(ctx.guild_id, ctx.channel_id)
	# 		connect_to_transmission(other_server, other_server_channel.id)

	# 		await asyncio.gather(
	# 			self.on_transmission(ctx.user, message, ctx.guild_id),
	# 			self.on_transmission(other_server_ctx.user, other_server_message, other_server)
	# 		) # type: ignore
	@transmit.subcommand(sub_cmd_description="Transmit messages to another server")
	@integration_types(guild=True, user=False)
	@contexts(bot_dm=False)
	async def connect(self, ctx: SlashContext):
		if ctx.guild is None or ctx.guild_id is None:
			return

		await ctx.defer()
		server_data: ServerData = await ServerData(_id=ctx.guild_id).fetch()
		trans = get_transmission(ctx.guild_id)

		if trans:
			return await fancy_message(ctx, "[ This server is already transmitting! ]", ephemeral=True)

		if available_initial_connections(server_data.transmissions.blocked_servers):
			trans = create_connection(ctx.guild_id, ctx.channel_id)

			embed = await self.embed_manager("initial_connection")

			cancel = Button(
				style=ButtonStyle.DANGER,
				label="Cancel",
				custom_id="haha cancel go brrr",
			)

			msg = await ctx.send(embeds=embed, components=cancel)

			task = asyncio.create_task(ctx.client.wait_for_component(components=cancel))

			while not connection_alive(trans):
				done, _ = await asyncio.wait({task}, timeout=1)

				if not done:
					continue

				remove_connection(trans)

				button_ctx: Component = task.result()

				await button_ctx.ctx.defer(edit_origin=True)

				embed = make_cancel_embed("manual", ctx.guild.name, button_ctx.ctx)

				await msg.edit(embeds=embed, components=[])
				return

			await increment_value(ctx, "times_transmitted", 1, ctx.user)

			await self.on_transmission(ctx, msg)

			return

		embed = await self.embed_manager("initial_connection")

		msg = await ctx.send(embeds=embed)

		await increment_value(ctx, "times_transmitted", 1, ctx.user)

		connect_to_transmission(ctx.guild_id, ctx.channel_id)
		await self.on_transmission(ctx, msg)
		return

	async def on_transmission(self, ctx: SlashContext, msg: Message):
		user = ctx.user
		server_id = ctx.guild_id
		if not server_id:
			return
		# loc = Localization(ctx)
		trans: Transmission | None = get_transmission(server_id)
		if not trans:
			return
		if (
			not connection_alive(trans) or trans.connection_b is None
		):  # NOTE: part after "or" is for python linter i'm not sure why it says that connection_b may be null 5 lines below
			return

		other_server: Guild | None
		if server_id == trans.connection_a.server_id:
			other_server = await self.client.fetch_guild(trans.connection_b.server_id)
		else:
			other_server = await self.client.fetch_guild(trans.connection_a.server_id)
		if not other_server:
			return

		server_data: ServerData = await ServerData(_id=server_id).fetch()
		await server_data.transmissions.known_servers.append(str(other_server.id))

		# guilds = [
		# 	await ctx.client.fetch_guild(id) or id
		# 	for id in list(set(server_data.transmissions.known_servers + server_data.transmissions.blocked_servers))
		# ]
		# known_servers = {
		# 	guild.id if isinstance(guild, Guild) else guild: guild.name
		# 	if isinstance(guild, Guild)
		# 	else (await lformat(loc, loc.l("transmit.autocomplete.unknown_server"), server_id=guild), True)
		# 	for guild in guilds
		# }

		btn_id = uuid.uuid4()

		disconnect = Button(style=ButtonStyle.DANGER, label="Disconnect", custom_id=str(btn_id))

		async def check_button(component: Component):
			if user.id == component.ctx.user.id:
				return True
			else:
				await component.ctx.send(
					f"[ Only the initiator of this transmission ({user.mention}) can cancel it! ]",
					ephemeral=True,
				)
				return False

		task = asyncio.create_task(self.client.wait_for_component(components=disconnect, check=check_button))

		disconnect_timer = 600

		embed = await self.embed_manager("connected")
		embed.description = f"[ Currently connected to **{other_server.name}**! ]"

		while connection_alive(trans):
			done, _ = await asyncio.wait({task}, timeout=1)

			if not done:
				if disconnect_timer % 10 == 0:
					time = ftime(disconnect_timer)

					embed.set_footer(text=f"Transmission will end in {time}.")

					await msg.edit(embeds=embed, components=disconnect)

				disconnect_timer -= 1

				if disconnect_timer == 30:
					await msg.reply("[ Transmission will end in 30 seconds. ]")

				if disconnect_timer == 0:
					embed = make_cancel_embed("timeout", server_name=other_server.name)

					remove_connection(trans)
					trans = None
					await msg.edit(embeds=embed, components=[])
					await msg.reply(embeds=embed)
					return

				continue  # * Important

			remove_connection(trans)
			# what to show to server that did cancel ↓
			await msg.edit(
				embeds=make_cancel_embed("casual", other_server.name, task.result().ctx),
				components=[],
			)
			await msg.reply(embeds=make_cancel_embed("manual", other_server.name, task.result().ctx))

			return
		# what to show to server who didn't cancel ↓
		await msg.edit(embeds=make_cancel_embed("casual", other_server.name), components=[])
		await msg.reply(embeds=make_cancel_embed("server", other_server.name))

		return remove_connection(trans)

	class TransmitUser:
		name: str
		id: int
		image: str

		def __init__(self, name, u_id, image):
			self.name = name
			self.id = u_id
			self.image = image

	async def check_anonymous(
		self,
		guild_id: int,
		d_user: User | Member,
		connection: Connection,
		server_data: ServerData,
	):
		user: TransmissionCommands.TransmitUser
		if isinstance(d_user, Member):
			d_user = d_user.user
		if server_data.transmissions.anonymous:
			i = 0

			selected_character = {}

			for i, character in enumerate(connection.characters):
				if character["id"] == 0 or character["id"] == d_user.id:
					user = TransmissionCommands.TransmitUser(
						character["Name"],
						d_user.id,
						f"https://cdn.discordapp.com/emojis/{character['Image']}.png",
					)

					connection.characters[i].update({"id": d_user.id})

					selected_character = character

					return user

			user = TransmissionCommands.TransmitUser(selected_character["name"], d_user.id, selected_character["image"])
		else:
			user = TransmissionCommands.TransmitUser(d_user.username, d_user.id, d_user.display_avatar.url)

		return user

	@listen()
	async def on_message_create(self, event: MessageCreate):
		message = event.message
		channel = message.channel
		guild = message.guild

		if channel.type == ChannelType.DM:
			return

		if message.author.id == self.client.user.id:
			return

		if guild is None:
			return
		t = get_transmission(guild.id)
		if not t:
			return

		if not connection_alive(t) or t.connection_b is None:
			return

		server_data: ServerData = await ServerData(_id=guild.id).fetch()

		first_server = t.connection_a
		second_server = t.connection_b

		can_pass = False
		other_connection: TYPE_ALL_CHANNEL | None
		allow_images = True
		if first_server.channel_id == channel.id:
			can_pass = True
			user = await self.check_anonymous(guild.id, message.author, first_server, server_data)
			other_connection = await self.client.fetch_channel(second_server.channel_id)
			allow_images = server_data.transmissions.allow_images

		if second_server.channel_id == channel.id:
			can_pass = True
			user = await self.check_anonymous(guild.id, message.author, second_server, server_data)
			other_connection = await self.client.fetch_channel(first_server.channel_id)
			allow_images = server_data.transmissions.allow_images

		if can_pass:
			embed = await self.message_manager(message, user, allow_images)
			if isinstance(other_connection, TYPE_MESSAGEABLE_CHANNEL):
				await other_connection.send(embeds=embed)
			else:
				raise TypeError("tried to send message in a channel where i can't send messages :mumawomp:")

	async def message_manager(self, message: Message, user: TransmitUser, allow_images: bool):
		final_text = message.content

		embed = Embed(
			color=Colors.DARKER_WHITE, url="https://theworldmachine.xyz"
		)  # url used for putting more than 1 image into the embed, see Embed.add_image method description
		embed.set_author(name=user.name, icon_url=user.image)

		overflow_check = True

		def overflow():
			nonlocal overflow_check
			nonlocal final_text
			if overflow_check:
				overflow_check = False
				final_text += "\n\n"

		for attachment in message.attachments:
			if attachment.content_type and attachment.content_type.startswith("image/"):
				if allow_images and len(embed.images) < 3:
					embed.add_image(image=attachment.url)
				else:
					overflow()
					final_text += f"{attachment.url} "
					if allow_images:
						embed.set_footer("embeds support up to 4 images")
			else:
				overflow()
				final_text += f"{attachment.url} "

		embed.description = final_text

		return embed

	async def embed_manager(self, embed_type: Literal["connected", "initial_connection"]):
		if embed_type == "initial_connection":
			return Embed(
				title="Transmission Starting!",
				description=f"Waiting for a connection... {emojis['icons']['loading']}",
				color=Colors.DEFAULT,
			)
		if embed_type == "connected":
			return Embed(title="Connected!", color=Colors.GREEN)


def make_cancel_embed(
	cancel_reason: Literal["manual", "server", "timeout", "casual"],
	server_name: str,
	button_ctx=None,
):
	author = button_ctx.author.mention if button_ctx else "Someone"
	match cancel_reason:
		case "manual":
			return Embed(
				title="Transmission Cancelled.",
				description=f"{author} cancelled the transmission.",
				color=Colors.WARN,
			)
		case "server":
			return Embed(
				title="Transmission Cancelled.",
				description="The other server cancelled the transmission.",
				color=Colors.RED,
			)
		case "timeout":
			return Embed(
				title="Transmission Ended.",
				description="You ran out of transmission time.",
				color=Colors.DEFAULT,
			)
		case "casual":
			return Embed(description=f"-# the transmission with {server_name} has ended")
		case _:
			raise ValueError("cancel_reason argument must be one of 'manual', 'server' or 'timeout'")


def setup(bot):
	TransmissionCommands(bot)
