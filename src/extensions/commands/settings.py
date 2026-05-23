from interactions import (
	AutocompleteContext,
	Embed,
	Extension,
	Guild,
	GuildText,
	InputText,
	MessageableMixin,
	Modal,
	ModalContext,
	OptionType,
	Permissions,
	SlashContext,
	TextStyles,
	contexts,
	integration_types,
	modal_callback,
	slash_command,
	slash_option,
)

from utilities.config import get_config
from utilities.database.schemas import ServerData
from utilities.localization.localization import Localization, locale_format
from utilities.localization.minis import put_mini
from utilities.message_decorations import Colors, fancy_message


class SettingsCommands(Extension):
	@slash_command(description="Configure the behavior of The World Machine for this server")
	@integration_types(guild=True, user=False)
	@contexts(bot_dm=False)
	async def settings(self, ctx: SlashContext):
		pass

	async def channel_permission_check(self, loc, ctx: SlashContext, channel: GuildText) -> bool:
		assert ctx.guild is not None
		if not isinstance(channel, MessageableMixin):
			await fancy_message(
				ctx,
				await locale_format(loc, loc.get("errors.channel_not_messageable", prefix_override="commands.settings.server")),
				color=Colors.BAD,
			)
			return False
		required_perms = Permissions.SEND_MESSAGES | Permissions.VIEW_CHANNEL | Permissions.ATTACH_FILES
		channel_perms = channel.permissions_for(ctx.guild.me)
		has_perms = (channel_perms & required_perms) == required_perms
		if not has_perms:
			await fancy_message(
				ctx,
				await locale_format(loc, loc.get("errors.channel_insufficient_perms", prefix_override="commands.settings.server")),
				color=Colors.BAD,
			)
		return True

	async def botmember_permission_check(self, loc, ctx: ModalContext | SlashContext):
		assert ctx.guild is not None
		assert ctx.member is not None
		member = ctx.guild.get_member(ctx.user.id)
		if not member:
			await fancy_message(
				ctx,
				await locale_format(loc, loc.get("errors.weird_edgecase_number_0", prefix_override="commands.settings.server")),
				color=Colors.BAD,
				ephemeral=True,
			)
			return False

		if not ctx.member.has_permission(Permissions.MANAGE_GUILD):
			await fancy_message(
				ctx,
				await locale_format(loc, loc.get("errors.missing_permissions", prefix_override="commands.settings.server")),
				color=Colors.BAD,
				ephemeral=True,
			)
			return False

		return True

	async def shortcut(
		self, ctx: ModalContext | SlashContext, prefix: str | None = None, defer: bool = True
	) -> tuple[Localization | None, ServerData | None]:
		if prefix is None:
			prefix = "commands.settings.server"
		assert ctx.guild is not None
		loc = Localization(ctx, prefix=prefix)
		if not await self.botmember_permission_check(loc, ctx):
			return (None, None)
		if defer:
			await ctx.defer(ephemeral=True)
		server_data: ServerData = await ServerData(ctx.guild.id).fetch()
		return (loc, server_data)

	transmissions = settings.group(name="transmissions")

	@transmissions.subcommand(
		sub_cmd_name="enabled",
		sub_cmd_description="Toggle this server's ability to receive calls",
	)
	@slash_option(
		description="default: True",
		name="value",
		opt_type=OptionType.BOOLEAN,
		required=True,
	)
	async def transmissions_enabled(self, ctx: SlashContext, value: bool):
		loc, server_data = await self.shortcut(ctx, prefix="commands.settings.server.transmissions.enabled")
		if not loc or not server_data:
			return
		await server_data.transmissions.update(disabled=not value)

		return await fancy_message(
			ctx,
			await locale_format(loc, loc.get(str(value).lower())),
			ephemeral=True,
		)

	@transmissions.subcommand(
		sub_cmd_name="channel",
		sub_cmd_description="Channel to be used by default when accepting calls",
	)
	@slash_option(
		description="(omit option to reset) default: Current",
		name="channel",
		opt_type=OptionType.CHANNEL,
	)
	async def transmissions_channel(self, ctx: SlashContext, channel: GuildText | None = None):
		loc, server_data = await self.shortcut(ctx, prefix="commands.settings.server.transmissions.channel")
		if not loc or not server_data:
			return

		if channel is None:
			await server_data.transmissions.update(channel_id=None)
			return await fancy_message(ctx, await locale_format(loc, loc.get("none")), ephemeral=True)

		if not await self.channel_permission_check(loc, ctx, channel):
			return

		await server_data.transmissions.update(channel_id=str(channel.id))
		return await fancy_message(
			ctx,
			await locale_format(loc, loc.get("some"), channel=channel.mention),
			ephemeral=True,
		)

	@transmissions.subcommand(
		sub_cmd_name="images",
		sub_cmd_description="Toggle embedding images when transmitting",
	)
	@slash_option(
		description="default: True",
		name="value",
		opt_type=OptionType.BOOLEAN,
		required=True,
	)
	async def transmissions_images(self, ctx: SlashContext, value: bool):
		loc, server_data = await self.shortcut(ctx, prefix="commands.settings.server.transmissions.images")
		if not loc or not server_data:
			return

		await server_data.transmissions.update(allow_images=value)
		return await fancy_message(
			ctx,
			await locale_format(loc, loc.get(str(value).lower())),
			ephemeral=True,
		)

	@transmissions.subcommand(
		sub_cmd_name="anonymous",
		sub_cmd_description="Whether transmission receivers are shown Oneshot characters instead of actual people from the server",
	)
	@slash_option(
		description="default: False",
		name="value",
		opt_type=OptionType.BOOLEAN,
		required=True,
	)
	async def transmissions_anonymous(self, ctx: SlashContext, value: bool):
		loc, server_data = await self.shortcut(ctx, prefix="commands.settings.server.transmissions.anonymous")
		if not loc or not server_data:
			return

		await server_data.transmissions.update(anonymous=value)

		return await fancy_message(
			ctx,
			await locale_format(loc, loc.get(str(value).lower())),
			ephemeral=True,
		)

	@transmissions.subcommand(
		sub_cmd_name="block",
		sub_cmd_description="Toggle blocking a server from being able to call",
	)
	@slash_option(
		description="The server's ID",
		name="server",
		opt_type=OptionType.STRING,
		required=True,
		autocomplete=True,
	)
	async def transmissions_block(self, ctx: SlashContext, server: str):
		loc, server_data = await self.shortcut(ctx, prefix="commands.settings.server.transmissions.block")
		if not loc or not server_data:
			return

		blocklist = server_data.transmissions.blocked_servers

		try:
			server_id = int(server)
			guild = ctx.client.get_guild(server_id)
		except ValueError:
			return await fancy_message(
				ctx,
				embed=Embed(
					description=f"{await locale_format(loc, loc.get('errors.invalid_server_id', prefix_override='commands.settings.server'))}\n-# {await locale_format(loc, loc.get('errors.get_server_id', prefix_override='commands.settings.server'))}",
					color=Colors.BAD,
				),
			)
		if str(server_id) in blocklist:
			await blocklist.remove(str(server_id))
		else:
			await blocklist.append(str(server_id))

		return await fancy_message(
			ctx,
			await locale_format(
				loc,
				loc.get(str(str(server_id) in blocklist).lower()),
				server_name=guild.name if guild else server_id,
			)
			+ (
				(
					"\n-# "
					+ await locale_format(loc, loc.get("errors.uncached_server", prefix_override="commands.settings.server"))
				)
				if not guild
				else ""
			),
			ephemeral=True,
		)

	@transmissions_block.autocomplete("server")
	async def block_server_autocomplete(self, ctx: AutocompleteContext):
		server_data: ServerData = await ServerData(_id=str(ctx.guild_id)).fetch()
		loc = Localization(ctx, prefix="commands.settings.server")
		guilds = [
			await ctx.client.fetch_guild(id) or id
			for id in list(set(server_data.transmissions.known_servers + server_data.transmissions.blocked_servers))
		]
		servers = {
			guild.id if isinstance(guild, Guild) else guild: guild.name
			if isinstance(guild, Guild)
			else (
				await locale_format(
					loc, loc.get("autocomplete.unknown_server", prefix_override="commands.transmit"), server_id=guild
				),
				True,
			)
			for guild in guilds
		}

		server = ctx.input_text

		filtered_servers = []

		for server_id, server_name in servers.items():
			if isinstance(server_name, tuple):
				filtered_servers.append({"name": server_name[0], "value": server_id})
				continue

			if server.lower() in server_name.lower():
				filtered_servers.append({"name": server_name, "value": server_id})

		await ctx.send(filtered_servers)

	welcome = settings.group(name="welcome")

	@welcome.subcommand(
		sub_cmd_name="enabled",
		sub_cmd_description="Whether to send the welcome textbox when someone joins",
	)
	@slash_option(
		description="default: False",
		name="value",
		opt_type=OptionType.BOOLEAN,
		required=True,
	)
	async def welcome_enabled(self, ctx: SlashContext, value):
		loc, server_data = await self.shortcut(ctx)
		if not loc or not server_data:
			return

		error = (
			""
			if not server_data.welcome.errored
			else await put_mini(loc, "minis.warnings.channel_lost", type="warn", pre="\n\n")
		)
		await server_data.welcome.update(disabled=not value)

		return await fancy_message(
			ctx,
			await locale_format(loc, loc.get(f"welcome.enabled.{str(value).lower()}")) + error,
			ephemeral=True,
		)

	@welcome.subcommand(
		sub_cmd_name="ping",
		sub_cmd_description="Whether to ping/notify the newcomers (shows the @mention regardless)",
	)
	@slash_option(
		description="default: False",
		name="value",
		opt_type=OptionType.BOOLEAN,
		required=True,
	)
	async def welcome_ping(self, ctx: SlashContext, value):
		loc, server_data = await self.shortcut(ctx)
		if not loc or not server_data:
			return

		error = (
			""
			if not server_data.welcome.errored
			else await put_mini(loc, "minis.warnings.channel_lost", type="warn", pre="\n\n")
		)
		await server_data.welcome.update(ping=value)

		return await fancy_message(
			ctx,
			await locale_format(loc, loc.get(f"welcome.ping.{str(value).lower()}")) + error,
			ephemeral=True,
		)

	@welcome.subcommand(sub_cmd_name="edit", sub_cmd_description="Edit this server's welcome message")
	async def welcome_edit(self, ctx: SlashContext):
		loc, server_data = await self.shortcut(ctx, defer=False, prefix="commands.settings.server.welcome.editor")
		if not loc or not server_data:
			return

		return await ctx.send_modal(
			Modal(
				InputText(
					label=await locale_format(loc, loc.get("input")),
					style=TextStyles.PARAGRAPH,
					custom_id="text",
					placeholder=await locale_format(loc, loc.get("placeholder")),
					max_length=get_config(
						"textbox.limits.frame-text-length",
						typecheck=int,
						ignore_None=True,
					)
					or 1423,
					required=False,
					value=server_data.welcome.message or loc.get("templates.default"),
				),
				title=await locale_format(loc, loc.get("title")),
				custom_id="welcome_message_editor",
			)
		)

	@modal_callback("welcome_message_editor")
	async def welcome_message_editor(self, ctx: ModalContext, text: str):
		loc, server_data = await self.shortcut(ctx, prefix="commands.settings.server.welcome")
		if not loc or not server_data:
			return

		config = server_data.welcome
		old_text = config.message
		new_text = text
		if new_text == loc.get("editor.templates.default") or new_text == "":
			new_text = None
		if old_text is None or old_text == "":
			old_text = loc.get("editor.templates.default")

		await config.update(message=new_text)
		Changed = "\n" + await locale_format(
			loc,
			loc.get("editor.changes"),
			old_text=f"```\n{old_text.replace('```', '` ``')}```",
			new_text=f"\n-# *{await locale_format(loc, loc.get('editor.new_none'))}*"
			if new_text is None
			else f"```\n{text.replace('```', '` ``')}```",
		)
		warn = (
			""
			if not config.disabled
			else await put_mini(
				loc,
				"minis.notes.welcome_disabled",
				user_id=ctx.user.id,
				pre="\n\n",
			)
		)
		error = "" if not config.errored else await put_mini(loc, "minis.warnings.channel_lost", type="warn", pre="\n\n")

		await fancy_message(
			ctx,
			await locale_format(loc, loc.get("editor.done")) + Changed + warn + error,
			ephemeral=True,
		)

	@welcome.subcommand(
		sub_cmd_name="channel",
		sub_cmd_description="Where to send the welcome textboxes to",
	)
	@slash_option(
		description="(omit option to reset) default: Server Settings -> System Messages channel",
		name="channel",
		opt_type=OptionType.CHANNEL,
	)
	async def welcome_channel(self, ctx: SlashContext, channel: GuildText | None = None):
		loc, server_data = await self.shortcut(ctx)
		assert ctx.guild is not None
		if not loc or not server_data:
			return
		config = server_data.welcome

		if channel and not await self.channel_permission_check(loc, ctx, channel):
			return
		if (
			not channel
			and ctx.guild.system_channel
			and not await self.channel_permission_check(loc, ctx, ctx.guild.system_channel)
		):
			return

		if channel is None:
			await config.update(channel_id=None, errored=False)
			return await fancy_message(ctx, await locale_format(loc, loc.get("welcome.channel.none")), ephemeral=True)

		error = "" if not config.errored else await put_mini(loc, "minis.warnings.channel_lost", type="warn", pre="\n\n")

		warn = ""
		if config.disabled:
			warn += await put_mini(
				loc,
				"minis.notes.welcome_disabled",
				user_id=ctx.user.id,
				pre="\n\n",
			)
		if not config.message:
			warn += await put_mini(
				loc,
				"minis.tips.welcome_edit",
				user_id=ctx.user.id,
				show_up_amount=15,
				pre="\n\n",
			)
		await config.update(channel_id=str(channel.id), errored=False)
		return await fancy_message(
			ctx,
			await locale_format(loc, loc.get("welcome.channel.some"), channel=channel.mention) + warn + error,
		)