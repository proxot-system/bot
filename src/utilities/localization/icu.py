from datetime import datetime
from traceback import print_exc
from typing import Any

from babel import Locale
from babel.numbers import format_currency, format_decimal, format_percent
from interactions import GLOBAL_SCOPE, BaseContext, Client, Snowflake, User
from pyicumessageformat import Parser

from utilities.config import get_token
from utilities.emojis import emojis, flatten_emojis, on_emojis_update
from utilities.localization.formatting import fnum
from utilities.misc import decode_base64_padded

emoji_dict = {}


def edicted(emojis):
	global emoji_dict
	f_emojis = flatten_emojis(emojis)
	emoji_dict = {name.replace("icons.", "").replace("_", " "): f_emojis[name] for name in f_emojis}


edicted(emojis)
on_emojis_update(edicted)

icu_parser = Parser({"allow_tags": False, "require_other": False})


async def icu_select(
	arguments: tuple[Any, Any, Any],
	variables: dict[str, Any],
	locale: str,
	client: Any | None = None,
	found_var: Any | None = None,
):
	value = str(found_var) if found_var is not None else ""
	options = arguments[2]

	if not isinstance(options, dict):
		return value

	result_branch = options.get(value, options.get("other", ""))

	return await render_icu(result_branch, variables, locale, client)


async def icu_notempty(
	arguments: tuple[Any, Any, Any],
	variables: dict[str, Any],
	locale: str,
	client: Any | None = None,
	found_var: Any | None = None,
):
	print(arguments)
	input = arguments[2]
	if found_var:
		return await render_icu(input, variables, locale, client)
	return ""


async def icu_selectordinal(
	arguments: tuple,
	variables: dict,
	locale: str,
	client: Any | None = None,
	found_var: Any | None = None,
):
	try:
		value = float(found_var) if found_var is not None else 0
	except (ValueError, TypeError):
		value = 0

	options = arguments[2]

	if not isinstance(options, dict):
		return str(value)

	exact_key = f"={int(value)}" if value.is_integer() else f"={value}"

	if exact_key in options:
		raw_result = options[exact_key]
	else:
		babel_locale = Locale.parse(locale, sep="-")
		category = babel_locale.ordinal_form(value)
		raw_result = options.get(category, options.get("other", ""))

	rendered_result = await render_icu(raw_result, variables, locale, client)

	if "#" in rendered_result:
		formatted_num = fnum(int(value) if value.is_integer() else value, locale)
		rendered_result = rendered_result.replace("#", formatted_num)

	return rendered_result


async def icu_plural(
	arguments: tuple[Any, Any, Any],
	variables: dict[str, Any],
	locale: str,
	client: Any | None = None,
	found_var: Any | None = None,
):
	try:
		value = float(found_var) if found_var is not None else 0
	except (ValueError, TypeError):
		value = 0

	options = arguments[2]
	if not isinstance(options, dict):
		return str(value)

	exact_key = f"={int(value)}" if value.is_integer() else f"={value}"
	if exact_key in options:
		raw_result = options[exact_key]
	else:
		babel_locale = Locale.parse(locale, sep="-")
		category = babel_locale.plural_form(value)

		raw_result = options.get(category, options.get("other", ""))

	rendered_result = await render_icu(raw_result, variables, locale, client)

	if "#" in rendered_result:
		formatted_num = fnum(int(value) if value.is_integer() else value, locale)
		rendered_result = rendered_result.replace("#", formatted_num)

	return rendered_result


async def icu_number(
	arguments: tuple[Any, Any, Any],
	variables: dict[str, Any],
	locale: str,
	client: Any | None = None,
	found_var: Any | None = None,
):
	try:
		value = float(found_var) if found_var is not None else 0
	except (ValueError, TypeError):
		return str(found_var)

	style = arguments[2]
	babel_locale = Locale.parse(locale, sep="-")

	if style == "percent":
		return format_percent(value, locale=babel_locale)
	elif style == "integer":
		return format_decimal(value, format="#,##0", locale=babel_locale)
	elif style == "currency":
		return format_decimal(value, locale=babel_locale)
	elif style and isinstance(style, str) and style.startswith("::currency/"):
		currency_code = style.split("/")[1]
		return format_currency(value, currency_code, locale=babel_locale)
	elif style and isinstance(style, str) and ("," in style or "." in style or "#" in style or "0" in style):
		return format_decimal(value, format=style, locale=babel_locale)
	else:
		return format_decimal(value, format=style if style else None, locale=babel_locale)


async def util_pretty_num(
	arguments: tuple[Any, Any, Any],
	variables: dict[str, Any],
	locale: str,
	client: Any | None = None,
	found_var: Any | None = None,
):
	input = found_var if found_var is not None else arguments[0]
	try:
		if isinstance(found_var, str):
			input = float(input)
			if input.is_integer():
				input = int(input)
		return fnum(input, locale)
	except (ValueError, TypeError):
		return input


async def icu_emoji(
	arguments: tuple[Any, Any, Any],
	variables: dict[str, Any],
	locale: str,
	client: Any | None = None,
	found_var: Any | None = None,
):
	global emoji_dict
	prop = arguments[0]
	if not prop:
		raise ValueError("no emoji name passed")
	if prop not in emoji_dict:
		raise ValueError(f"unknown emoji '{prop}'")

	return emoji_dict[prop]


bot_id = decode_base64_padded(get_token().split(".")[0])


async def util_user(
	arguments: tuple[Any, Any, Any],
	variables: dict[str, Any],
	locale: str,
	client: Any | None = None,
	found_var: Any | None = None,
):
	user_id = str(found_var) if found_var else str(arguments[0])
	if user_id.lower() in (
		"twm",
		"the world machine",
		"theworldmachine",
		"the-world-machine",
		"proxot",
		"proxot-bot",
		"proxot bot",
		"bot",
	):
		user_id = bot_id
	try:
		Snowflake(int(user_id))
	except:
		return f"'{user_id}' is not a valid user id"
	prop = arguments[2]
	if user_id != str(bot_id):
		if not isinstance(client, Client):
			return ValueError("function unsupported")
		try:
			user = await client.fetch_user(user_id)
		except Exception as e:
			user = e
		if not isinstance(user, User):
			return f"could not fetch user from userid, '{user}'"
	if user:
		user_data = {
			"mention+(@username)": f"<@{user.id}> (@{user.username})",
			"displayname+(@username)": f"{user.display_name} (@{user.username})"
			if user.display_name != user.username
			else "@{user.username}",
			"mention": f"<@{user.id}>",
			"id": str(user.id),
			"username": user.username,
			"display_name": user.display_name,
		}
	elif user_id == str(bot_id):
		user_data = {
			"mention+(@username)": f"<@{bot_id}> (@The World Machine)",
			"displayname+(@username)": f"The World Machine",
			"id": bot_id,
			"mention": f"<@{bot_id}>",
			"username": "The World Machine",
			"display_name": "The World Machine",
		}
	else:
		return Exception("all ways of getting the user have failed and the doom has come")
	if prop not in user_data:
		raise ValueError(f"property '{prop}' not found in user ({user_data['username']}, {user_data['id']}) data")

	return user_data[prop]


async def util_slash(
	arguments: tuple[Any, Any, Any],
	variables: dict[str, Any],
	locale: str,
	client: BaseContext | None = None,
	found_var: Any | None = None,
):
	command_name = arguments[0][1:].replace("/", " ")
	id = "0"
	if isinstance(client, Client) and hasattr(client, "_interaction_lookup"):
		command = client._interaction_lookup.get(command_name)
		if command:
			id = command.get_cmd_id(GLOBAL_SCOPE)
			command_name = command.get_localised_name(locale)
	return f"</{command_name}:{id}>"


async def util_quote(
	arguments: tuple[Any, Any, Any],
	variables: dict[str, Any],
	locale: str,
	client: BaseContext | None = None,
	found_var: Any | None = None,
):
	input = found_var if found_var is not None else arguments[0]
	if not isinstance(input, str):
		input = str(input)
	return "\n".join(f"> {line}" for line in input.split("\n"))


DISCORD_TIMESTAMP_MAP = {
	("date", "short"): "d",
	("date", "medium"): "D",
	("date", "long"): ":3",
	("date", "full"): "F",
	("time", "short"): "t",
	("time", "medium"): "T",
	("time", "long"): ":3",
	("date", "relative"): "R",
	("time", "relative"): "R",
}


async def util_datetime(
	arguments: tuple[Any, Any, Any],
	variables: dict[str, Any],
	locale: str,
	client: Any | None = None,
	found_var: Any | None = None,
):
	val = found_var if found_var is not None else datetime.now().timestamp()
	if isinstance(val, datetime):
		seconds = int(val.timestamp())
	else:
		try:
			seconds = int(float(val))
		except (ValueError, TypeError):
			return Exception(f"invalid time passed '{val}'")

	icu_type = str(arguments[1]).lower() if arguments[1] else "date"
	icu_style = str(arguments[2]).lower() if arguments[2] else "long"

	discord_style = DISCORD_TIMESTAMP_MAP.get((icu_type, icu_style))

	if discord_style == ":3":
		return f"<t:{seconds}:f> (<t:{seconds}:R>)"

	if not discord_style:
		discord_style = "f"

	return f"<t:{seconds}:{discord_style}>"


async def util_fallback(
	arguments: tuple[Any, Any, Any],
	variables: dict[str, Any],
	locale: str,
	client: Any | None = None,
	found_var: Any | None = None,
):
	return f"{{{arguments[0]}{'' if not arguments[1] else ' , ' + arguments[1]}{'' if not arguments[2] else ' , ' + str(arguments[2])}}}"


icu_formatters = {
	"emoji": icu_emoji,
	"user": util_user,
	"command": util_slash,
	"pretty_num": util_pretty_num,
	"selectordinal": icu_selectordinal,
	"select": icu_select,
	"plural": icu_plural,
	"number": icu_number,
	"notempty": icu_notempty,
	"quote": util_quote,
	"time": util_datetime,
	"date": util_datetime,
}


async def parse_node(node: dict, variables, locale, client: Any | None = None):
	variable = node.get("name")
	if variable is None:
		return Exception("no variable passed")

	format_type = node.get("type")

	extra_format_arguments = node.get("format")
	options = node.get("options")

	arg3 = options if options is not None else extra_format_arguments

	if variable.startswith("/"):
		format_type = "command"

	if variable.startswith(">"):
		variable = variable[1:]
		format_type = "quote"

	if isinstance(variable, str) and "{" in variable and "}" in variable:
		variable = await render_icu(variable, variables, locale, client)

	if isinstance(format_type, str) and "{" in format_type and "}" in format_type:
		format_type = await render_icu(format_type, variables, locale, client)

	if variable in variables:
		found_var = variables[variable]
		var_exists = True
	else:
		found_var = None
		var_exists = False

	if not format_type and not arg3:
		if var_exists:
			return found_var
		return f"{{{variable}}}"

	if format_type in icu_formatters:
		try:
			fn = icu_formatters[format_type]
			return await fn(
				(variable, format_type, arg3),
				variables,
				locale,
				client,
				found_var=found_var,
			)
		except Exception as e:
			print_exc()
			errname = type(e).__name__
			if errname == "Exception":
				errname = "err"
			return Exception(f"{errname}: {e}")
	else:
		if var_exists:
			return found_var
		else:
			return await util_fallback(
				(variable, format_type, arg3),
				variables,
				locale,
				client,
				found_var=found_var,
			)


async def evaluate_ast(tree, variables, locale, client: Client | None):
	variables = {**variables, "_locale": locale}
	output = []
	for node in tree:
		parsed_node = None

		if isinstance(node, str):
			parsed_node = node
		elif isinstance(node, dict):
			parsed_node = await parse_node(node, variables, locale, client)
		else:
			parsed_node = Exception(f"node {node} has unexpected type for an icu tree")

		if not isinstance(parsed_node, (str, int, float)):
			parsed_node = f"<! {str(parsed_node)} !>"
		elif isinstance(parsed_node, (int, float)):
			parsed_node = str(parsed_node)
		output.append(parsed_node)

	return "".join(output)


async def render_icu(message, variables, locale, client: Client | None = None):
	if isinstance(message, list):
		return await evaluate_ast(message, variables, locale, client)

	if not isinstance(message, str):
		return str(message)
	tree = icu_parser.parse(message)
	return await evaluate_ast(tree, variables, locale, client)
