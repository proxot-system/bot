import asyncio
import re
from typing import Any

from interactions import (
	ActionRow,
	AllowedMentions,
	Button,
	ButtonStyle,
	ComponentContext,
	Embed,
	PartialEmoji,
	component_callback,
)

from utilities.emojis import make_emoji_cdn_url
from utilities.localization.localization import Localization, locale_format
from utilities.message_decorations import Colors
from utilities.misc import replace_numbers_with_emojis
from utilities.textbox.facepics import f_storage, get_facepic
from utilities.textbox.states import StateShortcutError, state_shortcut

FACEPIC_AT_START_REGEX = re.compile(r"^\\@\[[^\]]*\]")


def set_facepic_in_frame_text(text: str | None, face_path: str) -> str:
	new_face_command = f"\\@[{face_path}]"
	if not text:
		return new_face_command
	if FACEPIC_AT_START_REGEX.search(text):
		return FACEPIC_AT_START_REGEX.sub(new_face_command, text)
	else:
		return f"{new_face_command}{text.lstrip()}"


async def render_selector_ui(
	ctx: ComponentContext,
	state_id: str,
	frame_index: int,
	path: list[str],
	page: int = 0,
):
	loc = Localization(ctx, prefix="commands.textbox.create")
	loc_facepics = Localization(ctx, prefix="facepics")
	current_level = f_storage.facepics
	previous_level = {}
	location = "root"
	for part in path:
		location = "child"
		previous_level = current_level
		current_level = current_level.get(part, {})

	loc_path = ".".join(f'["{name}"]' for name in path)
	prev_loc_path = ".".join(f'["{name}"]' for name in path[:-1])
	name = (
		loc_facepics.get_string(f"{loc_path}._name", typecheck=Any, return_None_on_not_found=True) or path[-1]
		if len(path) > 0
		else None
	)

	def _other():
		return (
			current_level
			if isinstance(current_level, str)
			else previous_level.get(
				"icon",
				previous_level.get("Normal"),
			)
		)

	icon = (
		current_level.get("icon", current_level.get("Normal", _other()))
		if not isinstance(current_level, str)
		else _other()
	)
	is_icon_metadata_facepic = "icon" in previous_level and previous_level.get("icon") is icon

	description = loc_facepics.get_string(
		f"{loc_path if not is_icon_metadata_facepic else prev_loc_path}._description",
		typecheck=Any,
		return_None_on_not_found=True,
	)
	credits = loc_facepics.get_string(
		f"{loc_path if not is_icon_metadata_facepic else prev_loc_path}._credits",
		typecheck=Any,
		return_None_on_not_found=True,
	)
	expression = None
	if isinstance(current_level, str):
		if not is_icon_metadata_facepic:
			expression = name
		name = (
			loc_facepics.get_string(f"{prev_loc_path}._name", typecheck=Any, return_None_on_not_found=True) or path[-1]
			if len(path) > 0
			else None
		)
	embed = Embed(
		description=await locale_format(
			loc,
			loc.get_string("facepic_picker.layout"),
			location=location,
			name=name,
			expression=expression,
			description=description,
			credits=credits,
			frame_index=frame_index + 1,
		),
		color=Colors.DEFAULT,
	)
	if icon:
		embed.set_thumbnail(make_emoji_cdn_url(emoji_id=str(icon)))
	if isinstance(current_level, str):
		return await ctx.edit_origin(
			embed=embed,
			allowed_mentions=AllowedMentions(parse=[], roles=[], users=[]),
		)

	all_buttons: list[Button] = []

	for key, value in current_level.items():
		if key.startswith("__") or key.startswith("_"):
			continue

		new_path_str = "/".join(path + [key])

		if isinstance(value, dict):
			emoji = PartialEmoji(name="📂")
			if "icon" in value:
				emoji = PartialEmoji(id=value["icon"])
			elif "Normal" in value:
				emoji = PartialEmoji(id=value["Normal"])
			button = Button(
				style=ButtonStyle.BLURPLE,
				label=key + "/",
				emoji=emoji,
				custom_id=f"textbox_fs select {state_id} {frame_index} 0 #{new_path_str}",
			)
		else:
			button = Button(
				style=ButtonStyle.GRAY,
				label=key,
				emoji=PartialEmoji(id=value) if value else PartialEmoji(name="❔"),
				custom_id=f"textbox_fs select {state_id} {frame_index} {page} {new_path_str}",
			)
		all_buttons.append(button)

	MAX_BUTTONS = 25
	MAX_PER_ROW = 5
	free_slots = MAX_BUTTONS

	preliminary_slots = MAX_BUTTONS - (1 if page > 0 else 0) - (1 if path else 0)
	paging_active = len(all_buttons) > preliminary_slots

	rows: list[ActionRow] = []
	first_row: list[Button] = []
	path_str = "/".join(path)

	if page > 0:
		first_row.append(
			Button(
				style=ButtonStyle.BLURPLE,
				emoji="⬅️",
				custom_id=f"textbox_fs select {state_id} {frame_index} {page - 1} #{path_str}",
			)
		)
		free_slots -= 1

	if path:
		parent_path = "/".join(path[:-1])
		first_row.append(
			Button(
				style=ButtonStyle.BLURPLE,
				emoji="⬆️",
				custom_id=f"textbox_fs select {state_id} {frame_index} 0 #{parent_path}",
			)
		)
		free_slots -= 1

	if paging_active:
		free_slots -= 2

	buttons_per_page = free_slots
	start_index = page * buttons_per_page
	end_index = start_index + buttons_per_page

	page_actions = all_buttons[start_index:end_index]
	has_next_page = end_index < len(all_buttons)

	actions_to_add_to_first_row = min(len(page_actions), MAX_PER_ROW - len(first_row) - (2 if paging_active else 0))
	first_row.extend(page_actions[:actions_to_add_to_first_row])
	remaining_page_actions = page_actions[actions_to_add_to_first_row:]

	if paging_active:
		first_row.append(
			Button(
				style=ButtonStyle.GRAY,
				label=replace_numbers_with_emojis(str(page + 1)),
				custom_id="ignore",
				disabled=True,
			)
		)
	if has_next_page:
		first_row.append(
			Button(
				style=ButtonStyle.BLURPLE,
				emoji="➡️",
				custom_id=f"textbox_fs select {state_id} {frame_index} {page + 1} #{path_str}",
			)
		)

	if first_row:
		rows.append(ActionRow(*first_row))

	for i in range(0, len(remaining_page_actions), MAX_PER_ROW):
		rows.append(ActionRow(*remaining_page_actions[i : i + MAX_PER_ROW]))

	await ctx.edit_origin(
		embed=embed,
		components=rows,
		allowed_mentions=AllowedMentions(parse=[], roles=[], users=[]),
	)


init_selector_regex = re.compile(r"textbox_fs init (?P<state_id>-?\d+) (?P<frame_index>-?\d+)")


@component_callback(init_selector_regex)
async def init_facepic_selector(self, ctx: ComponentContext):
	match = init_selector_regex.match(ctx.custom_id)
	if not match:
		return
	state_id, frame_index_str = match.groups()
	await ctx.defer(ephemeral=True)
	await render_selector_ui(ctx, state_id, int(frame_index_str), path=[])


select_regex = re.compile(
	r"textbox_fs select (?P<state_id>-?\d+) (?P<frame_index>-?\d+) (?P<page>\d+)(?: (?P<noupd>\#)?(?P<path>.*))?$"
)


@component_callback(select_regex)
async def handle_facepic_selection(self, ctx: ComponentContext):
	await ctx.defer(edit_origin=True)
	from .create import respond as update_textbox

	match = select_regex.match(ctx.custom_id)
	if not match:
		return

	state_id, frame_index_str, page_str, noupd, path_str = match.groups()
	frame_index = int(frame_index_str)
	page = int(page_str)
	path = path_str.strip().split("/") if path_str and path_str.strip() else []

	if not noupd and path_str.strip():
		try:
			_, state, frame_data = await state_shortcut(ctx, state_id, frame_index)
		except StateShortcutError:
			return
		face_path = path_str.strip()
		face = await get_facepic(face_path)
		if face and face.icon is None and not face.path.startswith("https://"):
			if face.path == "Other/Your Avatar":
				face_path = ctx.user.avatar_url
		
		frame_data.text = set_facepic_in_frame_text(frame_data.text, face_path)

		await update_textbox(state.memory_leak, state_id, int(frame_index) or 0, type="loading", edit=True)
		asyncio.create_task(update_textbox(state.memory_leak, state_id, frame_index, edit=True))

	selected_item = f_storage.facepics
	for part in path:
		selected_item = selected_item.get(part)
		if selected_item is None:
			return await ctx.edit_origin()

	await render_selector_ui(ctx, state_id, frame_index, path, page)
