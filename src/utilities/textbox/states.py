from pathlib import Path
from typing import Any, Literal, Optional, Tuple, Union, get_args, overload

from utilities.localization.localization import Localization, locale_format
from utilities.message_decorations import fancy_message
from utilities.textbox.mediagen import Frame

states = {}
SupportedFiletypes = Literal["WEBP", "GIF", "APNG", "PNG", "JPEG"]
state_template = Path("src/utilities/textbox/template.ttb").read_text()


class StateOptions:
	filetype: SupportedFiletypes  # TODO: m,ake this use an enum
	send_to: Literal[1, 2, 3]  # TODO: m,ake this use an enum
	quality: int
	loops: int  # 0 means that it will loop forever.

	def __init__(
		self,
		filetype: SupportedFiletypes | None = "WEBP",
		send_to: Literal[1, 2, 3] | str | None = 1,
		quality: int | str | None = 100,
		loops: int | None = 0,
	):
		if filetype is None:
			filetype = "WEBP"
		filetype = filetype.upper()  # type:ignore
		if filetype not in get_args(SupportedFiletypes):
			raise ValueError(f"filetype must be one of {get_args(SupportedFiletypes)}")

		if send_to is None:
			send_to = 1
		self.filetype = filetype  # type:ignore
		send_to = int(send_to)  # type:ignore
		if send_to not in (1, 2, 3):
			raise ValueError("send_to must be 1, 2 or 3")
		self.send_to = send_to

		if quality is None:
			quality = 100
		quality = int(quality)
		if quality < 1 or quality > 100:
			raise ValueError("quality must be in the range 1..=100")

		self.quality = quality

		if loops is None or loops < 0:
			loops = 1
		self.loops = loops

	def __repr__(self):
		attrs = {k: getattr(self, k) for k in self.__annotations__}
		attrs_str = ", ".join(f"{k}={repr(v)}" for k, v in attrs.items())
		return f"StateOptions({attrs_str})"


class State:
	owner: int
	frames: list[Frame]
	options: StateOptions
	memory_leak: Any | None  # 🤑🤑🤑

	async def to_string(self, loc: Localization) -> str:
		frames = "\n".join([str(f) for f in self.frames])
		sloc = Localization(loc, prefix="commands.textbox.create")
		processed: str = await locale_format(
			sloc,
			state_template,
			comment=await locale_format(
				sloc,
				sloc.get("ttb.comment"),
				link="https://github.com/proxot-system/bot/blob/main/md/en/textbox/index.md#raw-file-editing-tbb",  # /md/{sloc.locale}/textbox
			),
			filetype=self.options.filetype,
			send_to=self.options.send_to,
			force_send=False,
			quality=self.options.quality,
			frames=frames,
		)
		return processed

	@staticmethod
	def from_string(input: str, owner: int) -> tuple["State", bool | None, int | None]:
		lines = input.split("\n")
		current = ""
		parsed_frames: list[Frame] = []
		StateOptions_parsed = {}
		StateOptions_allowed_keys = [
			"force_send",
			"filetype",
			"send_to",
			"quality",
			"frame_index",
			"loops",
		]
		i = 0
		for line in lines:
			i += 1
			if line.startswith("#> StateOptions <#"):
				current = "StateOptions"
				continue
			if line.startswith("#> Frames <#"):
				current = "Frames"
				continue
			if line.lstrip().startswith("#") or len(line) == 0:
				continue
			if current == "Frames":
				try:
					parsed_frames.append(Frame.from_string(line))
				except BaseException as e:
					raise ValueError(f"Failed to parse frame #{len(parsed_frames)} at line {i}!\n{e}") from e
				continue
			if current == "StateOptions":
				if "=" not in line:
					raise ValueError(f"Couldn't find the value to set at line {i} of StateOptions")
				key, value = line.split("=", maxsplit=1)
				if key not in StateOptions_allowed_keys:
					raise KeyError(
						f"Received invalid key '{key}' at line {i}, it should be one of: {','.join(StateOptions_allowed_keys)}"
					)

				try:
					if value == "":
						value = None
					if value:
						if key == "filetype" and value.upper() not in get_args(SupportedFiletypes):
							raise ValueError(f"must be one of {get_args(SupportedFiletypes)}")
						if key == "send_to":
							try:
								send_to = int(value)  # type:ignore
							except:
								raise ValueError("must be an integer, and one of (1, 2, 3)")
							if send_to not in (1, 2, 3):
								raise ValueError("must be one of (1, 2, 3)")
						if key == "quality":
							try:
								quality = int(value)
							except:
								raise ValueError("must be an integer, and in the range 1..=100")
							if quality < 1 or quality > 100:
								raise ValueError("must be in the range 1..=100")
						if key == "loops":
							try:
								loops = int(value)  # type:ignore
							except:
								raise ValueError("must be an integer")
							if loops < 0:
								raise ValueError("must not be less than 0")
				except ValueError as e:
					raise ValueError(f"`StateOptions:` '{key}' {e}. Got '{value}', at line {i}")
				StateOptions_parsed[key] = value
				continue

		force_send = StateOptions_parsed.get("force_send", False) == "True"
		if "force_send" in StateOptions_parsed.keys():
			del StateOptions_parsed["force_send"]
		frame_index = StateOptions_parsed.get("frame_index", None)
		if frame_index:
			try:
				frame_index = int(frame_index)
			except ValueError:
				raise ValueError("Could not convert frame_index to integer")
			if not (frame_index >= 0):
				raise ValueError("frame_index must be >= 0")
		if "frame_index" in StateOptions_parsed.keys():
			del StateOptions_parsed["frame_index"]
		return (
			State(
				owner=owner,
				frames=parsed_frames,
				options=StateOptions(**StateOptions_parsed),
			),
			force_send,
			frame_index,
		)

	def __init__(
		self,
		owner: int,
		memory_leak: Any | None = None,
		frames: list[Frame] | Frame | None = None,
		options: StateOptions | None = None,
	):
		self.memory_leak = memory_leak
		self.options = options if options else StateOptions()
		self.owner = owner
		self.frames = []
		if not frames:
			return
		if isinstance(frames, Frame):
			self.frames = [frames]
			return
		if isinstance(frames, list):
			i = 0
			for frame in frames:
				i += 1
				if not isinstance(frame, Frame):
					raise ValueError(f"Frame {i} is not of type Frame.\n{frame}")
				self.frames.append(frame)

	def __repr__(self):
		return (
			"State(\n"
			+ f"  owner={self.owner},\n"
			+ f"  frames: len()={len(self.frames)}; [\n"
			+ f"{',\n'.join(f'      {repr(frame)}' for frame in self.frames)}\n"
			+ f"  ]\n"  # noqa: F541
			+ f"  {self.options}\n"
			f")"
		)

	def get_frame(self, index: int) -> Frame:
		"""
		            Gets a frame from the frames list. Creates an empty frame if the passed index is one above the length of the frames

		Raises:
		    IndexError: If the passed index is out of bounds and is not length + 1
		"""
		if index < len(self.frames):
			return self.frames[index]
		elif index == len(self.frames):
			frame = Frame()
			self.frames.append(frame)
			return frame
		else:
			raise IndexError(f"Frame #{index} is out of bounds. The state only has {len(self.frames)} frames")


class StateShortcutError(Exception):
	pass


@overload
async def state_shortcut(
	ctx, state_id: str | int, frame_index: Literal[None], loc_prefix: str = "main", refresh_ctx: bool = False
) -> Tuple["Localization", "State"]: ...


@overload
async def state_shortcut(
	ctx, state_id: str | int, frame_index: str | int, loc_prefix: str = "main", refresh_ctx: bool = False
) -> Tuple["Localization", "State", "Frame"]: ...


async def state_shortcut(
	ctx, state_id: str | int, frame_index: Optional[str | int], loc_prefix: str = "commands.textbox.create", refresh_ctx: bool = False
) -> Union[Tuple["Localization", "State"], Tuple["Localization", "State", "Frame"]]:
	"""
	            Helper function for textbox to not have to get these variables all the time
	Raises:
	    StateShortcutError: If the state or frame cannot be found, or if the
	                        frame index is invalid. The user will be notified
	                        with an ephemeral message before the exception is raised.
	"""
	loc = Localization(ctx, prefix=loc_prefix)
	try:
		state: State = states[str(state_id)]
	except KeyError:
		await fancy_message(
			ctx,
			await locale_format(loc, loc.get("generic.errors.expired", prefix_override="main")) + f"\n-# **sid:** {str(state_id)}",
			components=[],
			ephemeral=True,
		)
		raise StateShortcutError(f"State with ID '{state_id}' not found.")

	if frame_index is None:
		return (loc, state)

	try:
		idx = int(frame_index)
	except ValueError:
		await fancy_message(
			ctx,
			await locale_format(loc, loc.get("errors.unknown_frame"), index=str(frame_index), total=len(state.frames)),
			ephemeral=True,
		)
		raise StateShortcutError(f"Frame index '{frame_index}' is not a valid integer.")

	try:
		frame_data: Frame = state.get_frame(idx)
	except IndexError:
		if idx == len(state.frames):
			state.frames.append(Frame())  # scary scary scary scary
		else:
			await fancy_message(
				ctx,
				await locale_format(loc, loc.get("errors.unknown_frame"), id=str(frame_index), total=len(state.frames)),
				ephemeral=True,
			)
			raise StateShortcutError(f"Frame with index '{idx}' not found in state '{state_id}'.")
	if refresh_ctx:
		state.memory_leak = ctx
	return (loc, state, frame_data)


def new_state(state_id, state: State):
	states[state_id] = state
	return states[state_id]
