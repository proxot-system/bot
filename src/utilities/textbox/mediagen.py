import inspect
import io
import re
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Literal, Sequence, get_args, get_origin

import apng
from grapheme import graphemes
from PIL import Image, ImageDraw, ImageFont

from utilities.config import get_config
from utilities.localization.localization import Localization, locale_format, source_loc
from utilities.misc import cached_get
from utilities.textbox.facepics import get_facepic
from utilities.textbox.parsing import (
	RGBA,
	CharCommand,
	CharSpeedModifier,
	ColorModifier,
	DelayCommand,
	FacepicChangeCommand,
	LineBreakCommand,
	LocaleCommand,
	init_token,
	parse_textbox_text,
)

SupportedFiletypes = Literal["WEBP", "GIF", "APNG", "PNG", "JPEG"]
SupportedLocations = Literal[
	"aleft",
	"acenter",
	"aright",
	"left",
	"center",
	"right",
	"bleft",
	"bcenter",
	"bright",
]
def sanitize(text: str) -> str:
	return text.replace("\\", "\\\\").replace("\n", "\\n")


def desanitize(text: str) -> str:
	return text.replace("\\n", "\n").replace("\\\\", "\\")


class SerializableData:
	_separator: str = ";"

	def __str__(self) -> str:
		"""Serializes the object to a string based on its fields."""
		parts = []
		for _field in fields(self):  # type: ignore
			value = getattr(self, _field.name)
			parts.append(str(value))
		return self._separator.join(parts)

	@classmethod
	def from_string(cls, data_string: str):
		"""Deserializes a string into an object of this class."""

		class_fields = fields(cls)  # type: ignore
		num_expected = len(class_fields)

		parts = data_string.split(cls._separator, num_expected - 1)

		if len(parts) != num_expected:
			raise ValueError(
				f"Invalid format for {cls.__name__}. Expected {num_expected} parts separated by '{cls._separator}', but got {len(parts)} in '{data_string}'"
			)

		kwargs = {}
		for _field, value_str in zip(class_fields, parts):
			kwargs[_field.name] = cls._parse_value(value_str, _field)

		return cls(**kwargs)

	@staticmethod
	def _parse_value(value_str: str, field: Any) -> Any:
		"""Helper to parse a string value into its target Python type."""
		origin = get_origin(field.type)
		args = get_args(field.type)

		if origin is Literal:
			if value_str not in args:
				raise ValueError(f"Value '{value_str}' is not a valid choice from {args}")
			return value_str
		if origin in (list, tuple):
			if not value_str:
				return origin()
			item_type = args[0] if args else str
			return origin(SerializableData._parse_value(item.strip(), item_type) for item in value_str.split(","))
		if origin is not None and any(
			isinstance(arg, type) and issubclass(arg, type(None)) for arg in args
		):  # Handles X | None
			if value_str == "None":
				return None
			actual_type = next(arg for arg in args if not issubclass(arg, type(None)))
			return SerializableData._parse_value(value_str, actual_type)

		if value_str == "" and field.type is not str:
			return None
		if field.type is bool:
			if value_str in ("True", "true", "+", "yes"):
				return True
			if value_str == ("False", "false", "-", "no"):
				return False
			raise ValueError(f"couldn't parse '{value_str}' as bool.")
		if field.type is int:
			return int(value_str)
		if field.type is str:
			return value_str

		if inspect.isclass(field.type) and issubclass(field.type, SerializableData):
			return field.type.from_string(value_str)

		return field.type(value_str)


@dataclass
class FrameOptions(SerializableData):
	animated: bool = True
	end_delay: int = 150
	end_arrow_bounces: int = 4
	end_arrow_delay: int = 150

	_separator: str = ";"

	def __init__(
		self,
		animated: bool | None = None,
		end_delay: int | None = None,
		end_arrow_bounces: int | None = None,
		end_arrow_delay: int | None = None,
		_separator: str | None = ";",
	):
		self.separator = ";"
		self.animated = True if animated is None else bool(animated)

		if isinstance(end_delay, int) and end_delay < 0:
			raise ValueError("end_delay must be above 0")
		self.end_delay = 150 if end_delay is None else end_delay

		if isinstance(end_arrow_bounces, int) and end_arrow_bounces < 0:
			raise ValueError("end_arrow_bounces must be above 0")
		self.end_arrow_bounces = 4 if end_arrow_bounces is None else end_arrow_bounces

		if isinstance(end_arrow_delay, int) and end_arrow_delay < 0:
			raise ValueError("end_arrow_delay must be above 0")
		self.end_arrow_delay = 150 if end_arrow_delay is None else end_arrow_delay

	def __repr__(self):
		attrs = {k: getattr(self, k) for k in self.__annotations__}
		attrs_str = ", ".join(f"{k}={repr(v)}" for k, v in attrs.items())
		return f"StateOptions({attrs_str})"


@dataclass
class Frame(SerializableData):
	text: str | None = None
	options: FrameOptions = field(default_factory=FrameOptions)

	_separator: str = ";"

	def __str__(self):
		return f"{{{self.options}}};{sanitize(self.text or '')}"

	@classmethod
	def from_string(cls, frame_string: str):
		try:
			if not frame_string.startswith("{"):
				frame_string = "{;;;;};" + frame_string
				# raise ValueError("String must start with '{' for options.")  # noqa: ERA001

			end_brace_idx = frame_string.find("}")
			if end_brace_idx == -1:
				raise ValueError("Mismatched braces: missing '}'.")

			if len(frame_string) <= end_brace_idx + 1 or frame_string[end_brace_idx + 1] != cls._separator:
				raise ValueError(f"Options block must be followed by a '{cls._separator}'.")

			options_raw = frame_string[1:end_brace_idx]
			sanitized_text = frame_string[end_brace_idx + 2 :]

			options = FrameOptions.from_string(options_raw)
			text = desanitize(sanitized_text) if sanitized_text else None

			return cls(options=options, text=text)
		except (ValueError, IndexError) as e:
			raise ValueError(
				f"Invalid Frame format. Expected '{{options}}{cls._separator}text', but got '{frame_string}'. {e}"
			) from e


not_empty_empty_face: FacepicChangeCommand = init_token(type="@")  # type:ignore
not_empty_empty_face.parse_input("clear")


async def render_frame(
	frame: Frame, animated: bool = True, loc: Localization = source_loc
) -> tuple[list[Image.Image], list[int]]:
	global not_empty_empty_face
	word_wrap = True
	background = Image.open(await cached_get(Path("src/data/images/textbox/backgrounds/", "normal.png")))
	borders = Image.open(await cached_get(Path("src/data/images/textbox/backgrounds/", "normal_borders.png")))
	burned_borders = borders.copy()
	background.resize((background.height, background.width + 500))
	font = ImageFont.truetype(await cached_get(Path(get_config("textbox.font")), force=True), 20)
	text = Image.new("RGBA", (background.width, 999999), color=(255, 255, 255, 0))
	text_x, text_y = 23, 16
	max_text_width = background.width - (20 * 2)
	# text_height = background.height - (17 * 2)
	images: list[Image.Image] = []
	durations: Sequence[int] = []

	frame_speed: float = 1.0

	def put_frame(duration: int, speed_adjust: bool = True):
		new = background.copy()
		new.paste(text, (text_x, int(text_y)), mask=text)
		new.paste(burned_borders, (0, 0), mask=burned_borders)
		images.append(new)
		if speed_adjust:
			duration = int(duration / frame_speed)
		durations.append(duration)

	facepic_present = False

	async def update_facepic(command: FacepicChangeCommand, delay: bool = False):
		nonlocal burned_borders
		nonlocal facepic_present
		nonlocal max_text_width
		burned_borders = borders.copy()
		facepic = await get_facepic(command.facepic)
		if facepic:
			facepic_present = True
			facepic = await facepic.get_image(size=96)
			facepic = facepic.resize((96, 96), resample=0)
			burned_borders.paste(facepic, (496, 16), mask=facepic.convert("RGBA"))
		else:
			facepic_present = False
			facepic = None
		if facepic_present and facepic:
			max_text_width = background.width - (20 * 2) - facepic.width + 10
		else:
			max_text_width = background.width - (20 * 2)
		if delay and animated:
			put_frame(0)

	def carriage_return():
		nonlocal text_y
		for i in range(4):
			for i in range(5):
				put_frame(0)
				text_y -= 5.0

	current_color = RGBA(255, 255, 255, 255)

	parsed = parse_textbox_text(frame.text) if frame.text else []
	print(parsed)
	text_offset = [0.0, 0.0]
	first_facepic_command = next((cmd for cmd in parsed if isinstance(cmd, FacepicChangeCommand)), None)
	if first_facepic_command and first_facepic_command.facepic != "":
		await update_facepic(not_empty_empty_face)
	i = 0
	while i < len(parsed):
		command = parsed[i]
		if isinstance(command, FacepicChangeCommand):
			if command.facepic != "":
				await update_facepic(command)
		elif isinstance(command, LineBreakCommand):
			text_offset[1] += 25.0
			text_offset[0] = 0.0
		elif isinstance(command, DelayCommand):
			put_frame(command.time, speed_adjust=False)
		elif isinstance(command, ColorModifier):
			current_color = command.color
		elif isinstance(command, CharSpeedModifier):
			frame_speed = command.speed if not (command.speed <= 0) else 0.25
		elif isinstance(command, LocaleCommand):
			out = None
			mt_loc = Localization(loc, prefix="")
			try:
				out = parse_textbox_text(await locale_format(mt_loc, mt_loc.get_string(command.path)))
			except Exception as e:
				out = ["[ " + str(e) + " ]"]
			i += 1
			parsed[i:i] = out
			continue
		elif isinstance(command, (str, CharCommand)):
			message = command
			if isinstance(command, CharCommand):
				# eventually i'll remove this duplicate if, after i handle the rest of the token types
				message = command.text

			if not isinstance(message, str):
				message = f"[ ermm? unexpected type from command, got {type(message)} ]"
			d = ImageDraw.Draw(text)
			cumulative_text = ""
			for word in re.findall(r"\S+\s*|\s+", message):  # TODO: regex alert
				if (
					text_offset[0] != 0
					and word_wrap
					and (d.textlength(word, font=font) + text_x + text_offset[0] + 1 > max_text_width)
				):
					text_offset[1] += 25.0
					text_offset[0] = 0.0
				for cluster in list(graphemes(word)):  # type: ignore
					if cluster is None:
						cluster: str = ""
					cumulative_text += cluster
					duration = 50
					match cluster:
						case "." | "!" | "?" | "．" | "？" | "！":
							duration = 600
						case "," | "，":
							duration = 100
					if text_offset[0] + 15 > max_text_width:
						text_offset[1] += 25.0
						text_offset[0] = 0.0
					if text_y + text_offset[1] > background.height - (17 * 2):
						carriage_return()
					try:
						d.text(
							(text_offset[0], text_offset[1]),
							cluster,
							font=font,
							fill=current_color,
						)
						text_offset[0] += d.textlength(
							cluster, font=font
						)  # TODO: there is a better way https://pillow.readthedocs.io/en/stable/reference/ImageText.html#example
					except:
						pass
					if animated:
						put_frame(duration)

		i += 1
	put_frame(0)
	return (images, durations)


# >>> bounce(2, 3)
# [1, 2, 3, 2, 1, 2, 3, 2, 1]  # noqa: ERA001
def bounce(times, height=3):
	pattern = []
	length = ((height + (height - 2)) * times) + 1
	cycle_length = (height * 2) - 2

	for i in range(length):
		position = i % cycle_length

		if position < height:
			value = position + 1
		else:
			value = (cycle_length - position) + 1

		pattern.append(value)

	return pattern


async def render_textbox_frames(
	frames: list[Frame],
	quality: int = 100,
	filetype: SupportedFiletypes = "WEBP",
	frame_index: int | None = None,
	loops: int = 0,
	loc: Localization = source_loc,
) -> io.BytesIO:
	if len(frames) == 0:
		raise ValueError("Provide atleast one frame")
	all_images: list[Image.Image] = []
	all_durations: list[int] = []
	buffer = io.BytesIO()
	if filetype in ("JPEG", "PNG"):
		if not frame_index:
			frame_index = 0
		frame = frames[int(frame_index)]
		image = (await render_frame(frame, False, loc))[0][0]
		if filetype == "JPEG":
			buffer = io.BytesIO()
			if image.mode == "RGBA":
				rgb_image = Image.new("RGB", image.size, (255, 255, 255))
				rgb_image.paste(image, mask=image.split()[3])
				rgb_image.save(buffer, format="JPEG", quality=quality)
			else:
				image.save(buffer, format="JPEG", quality=quality)
		else:
			image.save(
				buffer,
				format="PNG",
				compress_level=9
				- int(max(0, min(100, quality)) * 9 / 100),  #  quality = 0->100 = compress_level = 9->0
			)
		return buffer

	for frame in frames:
		images, durations = await render_frame(frame, frame.options.animated)
		all_images.extend(images)
		all_durations.extend(durations)

		# make the ending thing
		arrow = Image.open(await cached_get(Path("src/data/images/textbox/backgrounds/", "normal_arrow.png")))
		arrow_rgba = arrow.convert("RGBA")
		last_frame = all_images[-1]
		all_durations[-1] = frame.options.end_delay
		bounce_frames = [
			":3",
			last_frame.copy(),
			last_frame.copy(),
			last_frame.copy(),
		]
		bounce_frames[1].paste(arrow, (299, 119), arrow_rgba)
		bounce_frames[2].paste(arrow, (299, 119 - 1), arrow_rgba)
		bounce_frames[3].paste(arrow, (299, 119 - 2), arrow_rgba)

		for i in bounce(frame.options.end_arrow_bounces, 3):
			all_images.append(bounce_frames[i])
			all_durations.append(frame.options.end_arrow_delay)
	all_images.append(last_frame.copy())
	all_durations.append(150)

	lowest_fastest = 0
	match filetype:
		case "WEBP":
			lowest_fastest = 11
		case "GIF":
			lowest_fastest = 20
		case "APNG":
			lowest_fastest = 11
	# flooring the durations, because if it's lower than a certain number the browser/app just slows it down to 100ms i think? i'm not sure
	# here's a thing one of the developer working on webp said about this
	# https://groups.google.com/a/webmproject.org/g/webp-discuss/c/Yd0sstcZGlU/m/4PfkB4aVa8cJ?pli=1  # noqa: ERA001
	#
	# all of these are the lowest i could get in firefox/android discord app
	for i in range(len(all_durations)):
		if all_durations[i] <= 0:
			all_durations[i] = lowest_fastest
	match filetype:
		case "WEBP":
			all_images[0].save(
				buffer,
				format="WEBP",
				save_all=True,
				append_images=all_images[1:],
				duration=all_durations,
				quality=quality,
				loops=loops,
			)
		case "APNG":
			png_images = []
			for img in all_images:
				temp_buffer = io.BytesIO()
				img.save(temp_buffer, format="PNG")
				temp_buffer.seek(0)
				png_obj = apng.PNG.from_bytes(temp_buffer.getvalue())
				png_images.append(png_obj)

			animation = apng.APNG(
				num_plays=loops,
			)

			for i, png_obj in enumerate(png_images):
				animation.append(png_obj, delay=int(all_durations[i]), delay_den=1000)

			apng_bytes = animation.to_bytes()
			buffer = io.BytesIO(apng_bytes)
		case "GIF":
			all_images[0].save(
				buffer,
				format="GIF",
				save_all=True,
				append_images=all_images[1:],
				duration=all_durations,
				optimize=True,
				loops=loops,
			)
	buffer.seek(0)
	return buffer
