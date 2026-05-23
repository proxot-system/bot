from typing import Literal

from interactions import (
	Attachment,
	ContextMenuContext,
	Extension,
	Member,
	Message,
	OptionType,
	SlashCommandChoice,
	SlashContext,
	User,
	contexts,
	integration_types,
	message_context_menu,
	slash_command,
	slash_option,
	user_context_menu,
)

from utilities.config import get_config
from utilities.textbox.mediagen import SupportedFiletypes

from .create import (
	facepic_autocomplete as create_facepic_autocomplete,
)
from .create import (
	handle_components as create_handle_components,
)
from .create import (
	handle_edit_modal as create_handle_edit_modal,
)
from .create import (
	handle_update_text_modal as create_handle_update_text_modal,
)
from .create import (
	start as start_builder,
)
from .facepic_selector import handle_facepic_selection, init_facepic_selector
from .state import command_ as state_cmd


class TextboxCommands(Extension):
	start_builder = start_builder

	@message_context_menu(name="📓 message to textbox")
	@integration_types(guild=True, user=True)
	@contexts(guild=True, bot_dm=True, private_channel=True)
	async def from_message(self, ctx: ContextMenuContext):
		assert isinstance(ctx.target, Message), "hi linter"
		message = ctx.target
		return await self.start_builder(
			ctx,
			message.content,
			face_path=message.author.display_avatar.as_url(extension="png", size=96),
			force_send=None,
			send_to=3,
		)

	@user_context_menu(name="📓 avatar as textbox facepic")
	@integration_types(guild=True, user=True)
	@contexts(guild=True, bot_dm=True, private_channel=True)
	async def from_user(self, ctx: ContextMenuContext):
		who = ctx.target
		assert isinstance(who, (Member, User)), "hi linter"
		return await self.start_builder(
			ctx,
			face_path=who.display_avatar.as_url(extension="png", size=96),
			force_send=None,
			send_to=3,
		)

	@slash_command(
		name="textbox",
		description="Commands related to Textboxes",
	)
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def textbox(self, ctx: SlashContext):
		"""Base command for textboxes."""

	@textbox.subcommand(
		sub_cmd_name="create",
		sub_cmd_description="Make a textbox or a GIF dialogue between characters, like in OneShot",
	)
	@slash_option(
		name="text",
		description="What you want the character to say?",
		opt_type=OptionType.STRING,
		required=False,
		max_length=get_config("textbox.limits.frame-text-length", typecheck=int),
	)
	@slash_option(
		name="facepic",
		argument_name="face_path",
		description="Which facepic do you want on the textbox? (go back to this option to continue serching)",
		opt_type=OptionType.STRING,
		required=False,
		autocomplete=True,
	)
	@slash_option(
		name="animated",
		description="Do you want the text to animate? (default: true)",
		opt_type=OptionType.BOOLEAN,
		required=False,
	)
	@slash_option(
		name="force_send",
		description="For sending empty textboxes with 'send_to' option (default: false)",
		opt_type=OptionType.BOOLEAN,
		required=False,
	)
	@slash_option(
		description="What filetype do you want the output to be?",
		name="filetype",
		opt_type=OptionType.STRING,
		choices=[
			SlashCommandChoice(name="WEBP (default)", value="WEBP"),
			SlashCommandChoice(name="GIF", value="GIF"),
			SlashCommandChoice(name="APNG", value="APNG"),
			SlashCommandChoice(name="PNG", value="PNG"),
			SlashCommandChoice(name="JPEG", value="JPEG"),
		],
	)
	@slash_option(
		name="send_to",
		description="Where do you want the output to be sent? (pass all other options for it to render&send right away)",
		opt_type=OptionType.INTEGER,
		required=False,
		choices=[
			SlashCommandChoice(name="Don't (default)", value=1),
			SlashCommandChoice(name="DMs", value=2),
			SlashCommandChoice(name="This channel (here)", value=3),
		],
	)
	@slash_option(
		argument_name="tbb_file",
		name="from_tbb_file",
		description="Pass a file here to load a textbox dialogue from a file.tbb (overwrites any other options)",
		opt_type=OptionType.ATTACHMENT,
		required=False,
	)
	async def create(
		self,
		ctx: SlashContext,
		text: str = "",
		face_path: str | None = None,
		force_send: bool | None = False,
		animated: bool = True,
		tbb_file: Attachment | None = None,
		filetype: SupportedFiletypes | None = None,
		send_to: Literal[1, 2, 3] = 1,
	):
		return await start_builder(
			self,
			ctx=ctx,
			text=text,
			face_path=face_path,
			force_send=force_send,
			animated=animated,
			tbb_file=tbb_file,
			filetype=filetype,
			send_to=send_to,
		)

	facepic_autocomplete = create.autocomplete("facepic")(create_facepic_autocomplete)
	handle_components = create_handle_components
	handle_update_text_modal = create_handle_update_text_modal
	handle_edit_modal = create_handle_edit_modal

	init_facepic_selector = init_facepic_selector
	handle_facepic_selection = handle_facepic_selection

	state = textbox.subcommand(
		sub_cmd_name="state",
		sub_cmd_description="Debugging command for textboxes (bot developer only)",
	)(state_cmd)
