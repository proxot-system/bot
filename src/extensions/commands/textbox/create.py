import asyncio
import io
import re
from datetime import datetime
from traceback import print_stack
from typing import Any, Awaitable, Literal, get_args

from interactions import (
	ActionRow,
	AllowedMentions,
	Attachment,
	AutocompleteContext,
	BaseContext,
	Button,
	ButtonStyle,
	ComponentContext,
	ContextMenuContext,
	Embed,
	File,
	MessageFlags,
	Modal,
	ModalContext,
	ParagraphText,
	SlashCommandChoice,
	SlashContext,
	component_callback,
	modal_callback,
)
from interactions.models.discord.components import (
	ContainerComponent,
	FileComponent,
	MediaGalleryComponent,
	MediaGalleryItem,
	TextDisplayComponent,
	UnfurledMediaItem,
)

from utilities.config import debugging, get_config
from utilities.localization.localization import Localization, locale_format
from utilities.localization.minis import put_mini
from utilities.message_decorations import Colors
from utilities.misc import (
	BadResults,
	SortOption,
	fetch,
	filler_task,
	optionSearch,
	sanitize_filename,
)
from utilities.textbox.facepics import f_storage
from utilities.textbox.mediagen import Frame, SupportedFiletypes, render_textbox_frames
from utilities.textbox.states import (
	State,
	StateOptions,
	StateShortcutError,
	new_state,
	state_shortcut,
)

from .facepic_selector import set_facepic_in_frame_text

nomentions = AllowedMentions(parse=[])


async def get_avatar_from_mention(ctx: BaseContext, mention: str):
	try:
		user_id = mention.strip("<@!>")

		if not user_id.isdigit():
			raise Exception()

		user = await ctx.client.fetch_user(user_id)
		if not user:
			raise Exception()
		return user.avatar_url
	except:
		return "Other/NAVI"


async def start(
	self,
	ctx: SlashContext | ContextMenuContext,
	text: str = "",
	face_path: str | None = None,
	force_send: bool | None = False,
	animated: bool = True,
	tbb_file: Attachment | None = None,
	filetype: SupportedFiletypes | None = None,
	send_to: Literal[1, 2, 3] = 1,
):
	loading = asyncio.create_task(respond(ctx, type="loading"))
	state_id = str(ctx.id)  # state_id is the initial `/textbox create` interaction's id
	frame_index = 0
	if tbb_file:
		if not tbb_file.filename.endswith(".tbb"):
			return await respond(
				ctx,
				type="error",
				error=f"Filename of the file passed to 'from_tbb_file' has to end with `.tbb`, got: '{tbb_file.filename}'",
			)
		try:
			contents = (await fetch(tbb_file.url)).decode("utf-8")
		except BaseException as e:
			return await respond(
				ctx,
				type="error",
				error=f"Failed to decode the contents of the file. {e}",
			)
		try:
			parsed_state, force_send, frame_index = State.from_string(contents, owner=ctx.user.id)
		except BaseException as e:
			return await respond(ctx, type="error", error=e)
		new_state(state_id, parsed_state)
	else:
		if not animated:
			filetype = "WEBP" if animated else "PNG"
		if not filetype:
			filetype = "WEBP"

		if filetype not in get_args(SupportedFiletypes):
			filetype = "WEBP"

		if face_path:
			if face_path == "Other/Your Avatar":
				face_path = ctx.user.avatar_url
			elif face_path.startswith("<@"):
				face_path = await get_avatar_from_mention(ctx, face_path)

			text = set_facepic_in_frame_text(text, face_path)

		# init state
		new_state(
			state_id,
			State(
				owner=ctx.user.id,
				memory_leak=ctx,
				options=StateOptions(filetype=filetype, send_to=send_to),
				frames=Frame(text=text),
			),
		)
	await loading
	loading = asyncio.create_task(respond(ctx, state_id, frame_index or 0, type="loading", edit=True))
	if force_send or (send_to != 1 and (len(text) != 0 and face_path is not None)):
		await send_output(ctx, state_id, 0)

	return await respond(ctx, state_id, frame_index or 0, awaitable=loading)


def convert_to_sortoptions(item: Any, path: list[str] | None = None, recursive: bool = False):
	if path is None:
		path = []
	items = []
	for key, value in item.items():
		if key.startswith("__") or key == "icon":
			continue
		full_path = "/".join(path + [key])
		if isinstance(value, dict):
			if recursive:
				items.extend(convert_to_sortoptions(value, path + [key], recursive=True))
			else:
				items.append(SortOption(picked_name=full_path + "/", value=full_path))
		else:
			items.append(SortOption(picked_name=full_path, value=full_path))
	return items


async def facepic_autocomplete(self, ctx: AutocompleteContext):
	search_query = ctx.input_text
	tøp = []
	if not search_query or search_query == "":
		tøp.append(
			SlashCommandChoice(
				name="Start by selecting a folder, or @ someone (focus back on input to continue)",
				value="",
			)
		)
	choices: list[SortOption] = []

	path = [part for part in search_query.strip().split("/") if part != ""]
	selected_item = f_storage.facepics
	descended = []
	if not search_query == "":
		for part in path:
			got = selected_item.get(part)
			if isinstance(got, str):
				path = descended
				break
			selected_item = got
			descended.append(part)
			if selected_item is None:
				break
	if not selected_item:
		selected_item = f_storage.facepics
	if len(path) == 0 or (selected_item != f_storage.facepics and len(path) != 0):
		choices.extend(convert_to_sortoptions(selected_item, path))
	else:
		choices.extend(convert_to_sortoptions(selected_item, [], recursive=True))
	tøp = tøp[:5]
	completed_search = []
	try:
		completed_search = optionSearch(search_query, choices, 25 - len(tøp))
	except BadResults:
		tøp.append(SlashCommandChoice(name="Bad search query", value=""))
		completed_search = optionSearch(search_query, choices, 25 - len(tøp), ignore_bad_results=True)
	return await ctx.send(tøp + completed_search)


handle_components_regex = re.compile(
	r"textbox (?P<method>refresh|render|change_text|facepic_selector|delete_frame|edit) (?P<state_id>-?\d+) (?P<frame_index>-?\d+)$"
)


@component_callback(handle_components_regex)
async def handle_components(self, ctx: ComponentContext):
	match = handle_components_regex.match(ctx.custom_id)
	if match:
		a = match.groups()
		lena = len(a)
	if match is None or lena != 3:
		return ctx.edit_origin()
	method, state_id, frame_index = match.group("method", "state_id", "frame_index")
	try:
		loc, state, frame_data = await state_shortcut(ctx, state_id, frame_index, refresh_ctx=True)
	except StateShortcutError:
		return
	loading = filler_task()
	match method:
		case "change_text":
			return await init_change_text_flow(ctx, state_id, frame_index)
		case "delete_frame":
			loading = asyncio.create_task(respond(ctx, state_id, int(frame_index) or 0, type="loading", edit=True))
			del state.frames[int(frame_index)]
		case "edit":
			return await init_edit_flow(ctx, state_id, frame_index)
		case "render":
			loading = asyncio.create_task(respond(ctx, state_id, int(frame_index) or 0, type="loading", edit=True))
			await send_output(ctx, state_id, int(frame_index))

	await respond(ctx, state_id, int(frame_index), awaitable=loading)


async def send_output(
	ctx: ComponentContext | SlashContext | ContextMenuContext,
	state_id: str,
	frame_index: int,
):
	try:
		loc, state, frame_data = await state_shortcut(ctx, state_id, frame_index, loc_prefix="commands.textbox.create", refresh_ctx=True)
	except StateShortcutError:
		return
	pos = ""
	message = await ctx.respond(
		embed=Embed(
			description=await locale_format(loc, loc.get("monologue.rendering")) + pos,
			color=Colors.DARKER_WHITE,
		),
		ephemeral=True,
	)

	start = datetime.now()
	file = await render_to_file(ctx, state)
	end = datetime.now()
	took = start - end

	asyncio.create_task(
		ctx.edit(
			message=message,
			embed=Embed(
				description=await locale_format(loc, loc.get("monologue.sending")) + pos,
				color=Colors.DARKER_WHITE,
			),
		)
	)
	content = f"-# [ {ctx.user.mention} ]"

	try:
		if state.options.send_to == 3:
			if ctx.guild:
				sent_message = await ctx.channel.send(content=content, files=file, allowed_mentions=nomentions)
			else:
				sent_message = await ctx.send(content=content, files=file, allowed_mentions=nomentions)
		elif state.options.send_to == 2:
			sent_message = await ctx.author.send(files=file)
		elif state.options.send_to == 1:
			sent_message = await ctx.send(content=content, files=file, allowed_mentions=nomentions, ephemeral=True)
	except:  # when it fails to send a dm or a followup to an ephemeral message with a non-ephemeral message
		return await ctx.edit(
			message=message,
			embed=Embed(
				description=await locale_format(
					loc,
					loc.get(f"errors.failed_to_send{'_dm' if state.options.send_to == 3 else ''}"),
				),
				color=Colors.DARKER_WHITE,
			),
		)
	desc = await locale_format(loc, loc.get("monologue.done"))
	if debugging():
		desc += "\n-# " + await locale_format(
			loc, loc.get("monologue.debug"), time=took.total_seconds(), sid=state_id
		)
	if (
		state.options.filetype in ("WEBP", "GIF", "APNG") and sent_message and MessageFlags.EPHEMERAL in sent_message.flags
	):
		mini = await put_mini(loc, "minis.warnings.ephemeral", user_id=ctx.user.id, show_up_amount=9, type="warn")
		if mini != "":
			await ctx.edit(
				message=sent_message,
				content=f"{sent_message.content}\n{mini}",
				allowed_mentions=nomentions,
			)
	return await ctx.edit(message=message, embed=Embed(description=desc, color=Colors.DEFAULT))


async def render_to_file(
	ctx: ComponentContext | SlashContext | ModalContext | ContextMenuContext,
	state: State,
	frame_preview_index: int | None = None,
) -> File:
	loc = Localization(ctx, prefix="commands.textbox.create")

	frames = state.frames
	filetype = state.options.filetype

	if frame_preview_index is not None:
		filetype = "PNG"
		frames = [state.frames[int(frame_preview_index)]]
	filename = await locale_format(
		loc,
		loc.get(f"alt.{'single' if frame_preview_index is not None else 'multi'}_frame.filename"),
		frames=len(frames),
		timestamp=str(round(datetime.now().timestamp())),
	)

	buffer = await render_textbox_frames(frames, state.options.quality, filetype, loops=state.options.loops, loc=loc)
	buffer.seek(0)
	filename = filename + ("" if filetype == "APNG" else "." + filetype)

	return File(file=buffer, file_name=filename)  # TODO: alt text # , description=alt_text if alt_text else frame.text)


async def init_change_text_flow(ctx: ComponentContext | SlashContext, state_id: str, frame_index: str):
	try:
		loc, state, frame_data = await state_shortcut(ctx, state_id, frame_index, loc_prefix="commands.textbox.create", refresh_ctx=True)
	except StateShortcutError:
		return
	modal = Modal(
		ParagraphText(
			custom_id="new_text",
			required=False,
			value=frame_data.text,
			label=await locale_format(loc, loc.get("modal.edit_text.input.label"), index=int(frame_index) + 1),
			placeholder=await locale_format(loc, loc.get("modal.edit_text.input.placeholder")),
			min_length=0,
			max_length=get_config("textbox.limits.frame-text-length", typecheck=int),
		),
		custom_id=f"textbox update_text_finish {state_id} {frame_index}",
		title=await locale_format(
			loc,
			loc.get("modal.edit_text.title"),
			index=int(frame_index) + 1,
			total=len(state.frames),
		),
	)
	await ctx.send_modal(modal)


update_text_modal_regex = re.compile(r"textbox update_text_finish (?P<state_id>-?\d+) (?P<frame_index>-?\d+)$")


@modal_callback(update_text_modal_regex)
async def handle_update_text_modal(self, ctx: ModalContext, new_text: str):
	match = update_text_modal_regex.match(ctx.custom_id)
	if match is None or len(match.groups()) < 2:
		return
	state_id, frame_index = match.group("state_id", "frame_index")
	try:
		loc, state, frame_data = await state_shortcut(ctx, state_id, frame_index, loc_prefix="commands.textbox.create")
	except StateShortcutError:
		return
	# old_text = frame_data.text
	frame_data.text = new_text
	# if debugging():
	# 	asyncio.create_task(
	# 		fancy_message(
	# 			ctx,
	# 			await locale_format(loc, loc.get("modal.edit_text.response"), new_text=new_text, old_text=old_text),
	# 			ephemeral=True,
	# 		)
	# 	)
	loading = asyncio.create_task(respond(ctx, state_id, int(frame_index) or 0, type="loading"))
	await respond(ctx, state_id, int(frame_index), edit=True, awaitable=loading)


async def init_edit_flow(ctx: ComponentContext | SlashContext, state_id: str, frame_index: str):
	try:
		loc, state, frame_data = await state_shortcut(ctx, state_id, frame_index, loc_prefix="commands.textbox.create", refresh_ctx=True)
	except StateShortcutError:
		return
	frames = ""
	for frame in state.frames:
		frames += str(frame) + "\n"
	modal = Modal(
		ParagraphText(
			custom_id="updated_frames",
			required=False,
			value=frames,
			label=await locale_format(loc, loc.get("modal.edit_frames.input.label"), index=int(frame_index) + 1),
			placeholder=await locale_format(loc, loc.get("modal.edit_frames.input.placeholder")),
		),
		custom_id=f"textbox edit_finish {state_id} {frame_index}",
		title=await locale_format(
			loc,
			loc.get("modal.edit_frames.title"),
			index=int(frame_index) + 1,
			total=len(state.frames),
		),
	)
	await ctx.send_modal(modal)


edit_regex = re.compile(r"textbox edit_finish (?P<state_id>-?\d+) (?P<frame_index>-?\d+)$")


@modal_callback(edit_regex)
async def handle_edit_modal(self, ctx: ModalContext, updated_frames: str):
	match = edit_regex.match(ctx.custom_id)
	if match is None or len(match.groups()) < 2:
		return
	state_id, frame_index = match.group("state_id", "frame_index")
	try:
		loc, state, frame_data = await state_shortcut(ctx, state_id, frame_index)
	except StateShortcutError:
		return
	# old_frames = ""
	# for frame in state.frames:
	# 	old_frames += str(frame) + "\n"
	try:
		new_frames = [Frame.from_string(raw) for raw in updated_frames.split("\n")]
	except BaseException as e:
		return await ctx.send(f"Woopsie! {e}", ephemeral=True)
	state.frames = new_frames

	loading = asyncio.create_task(respond(ctx, state_id, int(frame_index) or 0, type="loading"))
	await respond(ctx, state_id, int(frame_index), edit=True, awaitable=loading)


async def respond(
	ctx: SlashContext | ComponentContext | ModalContext | ContextMenuContext | None,
	state_id: str | None = None,
	frame_index: int | None = None,
	type: Literal["normal", "loading", "error"] = "normal",
	edit: bool = True,
	warnings: list = [],
	error: Any | None = None,
	awaitable: Awaitable | None = None
):
	if ctx is None:
		raise ValueError("uhhh")
	if awaitable is None:
		awaitable = filler_task()
	components = []
	files = []
	content: str | None = None
	accent_color = Colors.BAD.value

	if type == "normal" or (type == "loading" and state_id is not None and frame_index is not None):
		assert state_id is not None and frame_index is not None

		try:
			loc, state, frame_data = await state_shortcut(ctx, state_id, frame_index, loc_prefix="commands.textbox.create")
		except StateShortcutError:
			return

		if warnings is None:
			warnings = []
		pos = ""
		if len(state.frames) > 1 or frame_index != 0:
			pos = f"\n-# {await locale_format(loc, loc.get('frame_position'), current=int(frame_index) + 1, total=len(state.frames))}"
		if debugging():
			pos += "\n-# **sid**: " + state_id
		next_frame_exists = len(state.frames) != int(frame_index) + 1
		print(state)
		if type != "loading":
			preview = await render_to_file(ctx, state, frame_preview_index=int(frame_index))
			filename = sanitize_filename(preview.file_name or "meow")
			files.append(preview)
		tbb = File(
			file=io.BytesIO((await state.to_string(loc)).encode("utf-8")),
			file_name=(filename.rsplit(".", maxsplit=1)[0] if type != "loading" else "generated") + ".backup.tbb",
		)
		files.append(tbb)
		components.extend(
			[
				FileComponent(file=UnfurledMediaItem(url=f"attachment://{tbb.file_name}")),
				MediaGalleryComponent(
					items=[
						MediaGalleryItem(
							media=UnfurledMediaItem(
								url=f"attachment://{filename}"
								if type != "loading"
								else "https://cdn.discordapp.com/attachments/1018976804117159976/1482946959835791411/attachment4-ezgif.com-coalesce.gif"
							)
						),
					]
				),
				ActionRow(
					Button(
						style=ButtonStyle.BLURPLE,
						label=await locale_format(
							loc,
							loc.get(f"button.text.{'edit' if frame_data.text else 'add'}"),
						),
						custom_id=f"textbox change_text {state_id} {frame_index}",
					),
					Button(
						style=ButtonStyle.BLURPLE,
						label=await locale_format(loc, loc.get("button.face")),
						custom_id=f"textbox_fs init {state_id} {frame_index}",
					),
					Button(
						style=ButtonStyle.BLURPLE,
						label=await locale_format(loc, loc.get("button.edit")),
						custom_id=f"textbox edit {state_id} {frame_index}",
					),
				),
				ContainerComponent(
					TextDisplayComponent(content=pos if len(pos) > 0 else "\n-# meow"),
					ActionRow(
						Button(
							style=ButtonStyle.GRAY,
							label=await locale_format(
								loc,
								loc.get("button.frame.previous"),
							),
							custom_id=f"textbox refresh {state_id} {int(frame_index) - 1}",
							disabled=int(frame_index) - 1 < 0,
						),
						Button(
							style=ButtonStyle.GREEN,
							label=await locale_format(
								loc,
								loc.get("button.render" + ("send" if state.options.send_to != 1 else "")),
								type=await locale_format(
									loc,
									loc.get(f"filetypes.{state.options.filetype}"),
								),
							),
							custom_id=f"textbox render {state_id} {frame_index}",
						),
						Button(
							style=ButtonStyle.DANGER if frame_data.text else ButtonStyle.GRAY,
							label=await locale_format(
								loc,
								loc.get(f"button.frame.{'clear' if len(state.frames) == 1 else 'delete'}"),
							),
							custom_id=f"textbox delete_frame {state_id} {frame_index}",
						),
						Button(
							style=ButtonStyle.GRAY,
							label=await locale_format(
								loc,
								loc.get(f"button.frame.{'next' if next_frame_exists else 'add'}"),
							),
							custom_id=f"textbox refresh {state_id} {int(frame_index) + 1}",
						),
					),
				),
			]
		)
	elif type == "loading":
		loc = Localization(ctx, "commands.textbox.create")
		content = await locale_format(loc, loc.get("loading"))
		accent_color = Colors.DEFAULT.value
		edit = False
	elif type == "error":
		content = str(error)
	else:
		print(f"Invalid response message type, got: {type}")
		print_stack()
		content = "Invalid response type, report this to the developers (you're not supposed to see this)"

	if len(components) == 0 and content and len(content) != 0:
		components.append(
			ContainerComponent(
				TextDisplayComponent(content=content),
				accent_color=accent_color,
			)
		)
	await awaitable
	if not edit:
		return await ctx.send(components=components, files=files, ephemeral=True)
	elif isinstance(ctx, ComponentContext) and not ctx.responded:
		return await ctx.edit_origin(components=components, files=files)
	else:
		return await ctx.edit(
			message=ctx.message_id if isinstance(ctx, ModalContext) else "@original",
			components=components,
			files=files,
		)
