import subprocess
from dataclasses import dataclass, field

# import sys
from traceback import print_exc
from typing import Literal, NamedTuple, Type

from utilities.config import get_config
from utilities.misc import ReprMixin

ALL_COMMAND_TYPES = Literal["c", "u", "f", "s", "d", "@"]


@dataclass
class FormatModifier(ReprMixin):
	unbolded: bool = False  #
	italic: bool = False
	underline: bool = False
	strikethrough: bool = False

	def parse_input(self, args: str | None):
		if not args or len(args) == 0:
			self.unbolded = False
			self.italic = False
			self.underline = False
			self.strikethrough = False
			return
		self.unbolded = "b" in args
		self.italic = "i" in args
		self.underline = "u" in args
		self.strikethrough = "s" in args


class RGBA(NamedTuple):
	r: int
	g: int
	b: int
	a: int = 255  # Default alpha


def csscolor(color: str) -> RGBA:
	try:
		result = subprocess.run(
			[get_config("paths.textbox.colorParser-Binary"), color],
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
			text=True,
			check=True,
		)
		output = result.stdout.strip()
	except subprocess.CalledProcessError as e:
		output = e.stdout.strip()
	except FileNotFoundError:
		raise ValueError("color parsing unsupported (binary not found)")

	if output.startswith("Error:"):
		raise ValueError(f"Invalid color, got: '{color}', {output}")

	try:
		return RGBA(*eval(output))
	except Exception as e:
		print_exc()
		raise ValueError(
			f"Kittystrophically failed to parse color: '{color}', output: '{output}'. Report this to the devs please"
		) from e


@dataclass
class ColorModifier(ReprMixin):
	color: RGBA = field(default_factory=lambda: RGBA(255, 255, 255, 255))

	def parse_input(self, args: str | None):
		args = args or "white"
		self.color = csscolor(args)


@dataclass
class LocaleCommand(ReprMixin):
	path: str = "commands.textbox.create.errors.nothing_passed"

	def parse_input(self, args: str | None):
		args = args or "commands.textbox.create.errors.nothing_passed"
		self.path = args


@dataclass
class LineBreakCommand(ReprMixin):
	def parse_input(self, args):
		return


@dataclass
class CharCommand(ReprMixin):
	text: str = ""

	def parse_input(self, args: str | None):
		args = args or ""
		self.text = args
		try:
			value: int
			if args.startswith("#"):
				value = int(args.lstrip("#"), 16)
			else:
				value = int(args)
			self.text = chr(value)
		except ValueError as e:
			raise ValueError(
				f"Invalid value passed to character command. Expected a hex value (e.g. #1F408) or an integer (e.g. 128008), got '{args}'"
			) from e


@dataclass
class DelayCommand(ReprMixin):
	time: int = 1

	def parse_input(self, args: str):
		args = args or ""
		try:
			self.time = int(args)
		except ValueError as e:
			raise ValueError(f"Invalid seconds passed to delay command. Expected an integer (1), got '{args}'") from e


@dataclass
class CharSpeedModifier(ReprMixin):
	speed: float = 1.0

	def parse_input(self, args: str):
		args = args or ""
		try:
			self.speed = float(args)
		except ValueError as e:
			raise ValueError(
				f"Invalid value passed to character speed modifier. Expected a float (1.0), got '{args}'"
			) from e


class FacepicChangeCommand(ReprMixin):
	facepic: str = ""

	def parse_input(self, args: str):
		self.facepic = args


TOKENS = (
	FormatModifier
	| ColorModifier
	| CharCommand
	| DelayCommand
	| CharSpeedModifier
	| FacepicChangeCommand
	| LineBreakCommand
)
COMMAND_MAP: dict[str, Type] = {
	"@": FacepicChangeCommand,
	"f": FormatModifier,
	"u": CharCommand,
	"c": ColorModifier,
	"s": CharSpeedModifier,
	"d": DelayCommand,
	"n": LineBreakCommand,
	"l": LocaleCommand,
}


def init_token(type: str) -> TOKENS:
	token_class = COMMAND_MAP.get(type)

	if token_class:
		return token_class()
	else:
		raise ValueError(
			f"Invalid token type '{type}'. Expected one of: {', '.join(COMMAND_MAP.keys())}"
		)  # TODO: remove this


class TokenParseError(ValueError):
	def __init__(self, message, position=None, command=None):
		super().__init__(message)
		self.position = position  # TODO: make this have two ints signifying start and end for red overlay in the output
		self.command = command

	def __str__(self):
		base = super().__str__()
		if self.position is not None:
			base += f" (position: {self.position})"
		if self.command is not None:
			base += f" (command: '{self.command}')"
		return base


def parse_textbox_text(input_str: str) -> list[str | TOKENS]:
	"""
	Parses a string of textbox text syntax into a list of tokens in the form of modifier/command classes or bare strings for normal text. Making thsi function lowered the amount of my braincells down to 12 from 5 :aga:

	Raises:
	                TokenParseError: Whenever there is an unclosed bracket
	"""
	tokens = []
	pos = 0
	length = len(input_str)
	input_str = input_str.replace("\n", "\\n")
	while pos < length:
		if input_str[pos] == "\\":
			# Handle escaped backslash ('\\')
			if pos + 1 < length and input_str[pos + 1] == "\\":
				if tokens and isinstance(tokens[-1], str):
					tokens[-1] += "\\"
				else:
					tokens.append("\\")
				pos += 2
				continue

			# Handle potential command ('\c')
			if pos + 1 < length:
				cmd_char = input_str[pos + 1]
				try:
					token = init_token(type=cmd_char)
					args_start = pos + 2

					if args_start < length and input_str[args_start] == "[":
						bracket_pos = args_start
						bracket_depth = 1
						scan_pos = args_start + 1

						while scan_pos < length and bracket_depth > 0:
							if input_str[scan_pos] == "[":
								bracket_depth += 1
							elif input_str[scan_pos] == "]":
								bracket_depth -= 1
								if bracket_depth == 0:
									token.parse_input(input_str[args_start + 1 : scan_pos])
									pos = scan_pos + 1
									break
							scan_pos += 1

						if bracket_depth > 0:
							raise TokenParseError(
								"Unclosed bracket",
								position=bracket_pos,
								command=f"\\{cmd_char}",
							)

						tokens.append(token)
						continue
					else:
						tokens.append(token)
						pos += 2
						continue
				except ValueError as e:
					print(e)
					if str(e).startswith("Invalid token type"):
						text_to_add = input_str[pos : pos + 2]
						if tokens and isinstance(tokens[-1], str):
							tokens[-1] += text_to_add
						else:
							tokens.append(text_to_add)
						pos += 2
						continue
					else:
						raise

			# lone backslash (e.g., at the end of the string)
			if tokens and isinstance(tokens[-1], str):
				tokens[-1] += "\\"
			else:
				tokens.append("\\")
			pos += 1
			continue

		next_cmd = input_str.find("\\", pos)
		if next_cmd == -1:
			text = input_str[pos:]
			pos = length
		else:
			text = input_str[pos:next_cmd]
			pos = next_cmd

		if text:
			tokens.append(text)

	merged = []
	for token in tokens:
		if merged and isinstance(token, str) and isinstance(merged[-1], str):
			merged[-1] += token
		else:
			merged.append(token)

	return merged
