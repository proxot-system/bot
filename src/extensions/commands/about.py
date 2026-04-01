from __future__ import annotations

import asyncio
import platform
from datetime import datetime, timezone
from typing import Literal, TypedDict, Union, overload

from interactions import (
	ActionRow,
	Button,
	ButtonStyle,
	ComponentContext,
	ContainerComponent,
	Embed,
	EmbedField,
	Extension,
	OptionType,
	SectionComponent,
	SlashContext,
	Snowflake,
	TextDisplayComponent,
	ThumbnailComponent,
	UnfurledMediaItem,
	component_callback,
	contexts,
	integration_types,
	slash_command,
	slash_option,
)
from yaml import full_load

from utilities.localization.formatting import amperjoin, fnum, ftime
from utilities.localization.localization import Localization, locale_format, source_loc
from utilities.message_decorations import Colors, fancy_message
from utilities.source_watcher import FileModifiedEvent, all_of, filter_file_suffix, filter_path, subscribe
from utilities.stats import get_stats, get_version


class Contributor:
	name: str
	country: str | None
	discord_id: Snowflake | None
	roles: list[str]
	links: list[str]

	def __init__(
		self,
		name: str,
		country: str | None = None,
		discord_id: Snowflake | None = None,
		roles: list[str] | None = None,
		links: list[str] | None = None,
	):
		self.name = name
		self.country = country
		self.discord_id = discord_id
		self.roles = roles or []
		self.links = links or []

	@overload
	async def render(self, loc: Localization, simple: Literal[True]) -> str: ...

	@overload
	async def render(
		self, loc: Localization, simple: Literal[False] = False
	) -> Union[SectionComponent, TextDisplayComponent]: ...

	async def render(
		self, loc: Localization, simple: bool = False
	) -> Union[str, SectionComponent, TextDisplayComponent]:
		ploc = Localization(loc, prefix="commands.info.about.contributors")
		roles = amperjoin([await locale_format(ploc, ploc.get(f"roles['{role}']")) for role in self.roles])
		links = " · ".join(item for item in [await format_link(ploc, link) for link in self.links] if item is not None)
		text: str | TextDisplayComponent = await locale_format(
			ploc,
			ploc.get(f"contrib.layout['{'simple' if simple else 'full'}']"),
			name=self.name,
			roles=roles,
			country_flags=self.country,
			links=links,
		)
		if simple:
			return text
		text = TextDisplayComponent(text)
		user = None if not ploc.client or not self.discord_id else (await ploc.client.fetch_user(self.discord_id))
		if not user:
			return text
		return SectionComponent(
			components=text,
			accessory=ThumbnailComponent(
				media=UnfurledMediaItem(url=user.display_avatar.as_url(size=4096)),
				description=await locale_format(ploc, ploc.get("contrib.pfp_alt_text")),
			),
		)


async def format_link(loc, link):
	lloc = Localization(loc, prefix="commands.info.about")
	split = link.split(": ")
	if len(split) != 2:
		return None
	service = split[0]
	url = split[1]

	service = await locale_format(lloc, lloc.get(f"buttons['{service}']"))

	return f"[`{service}`]({url})"


class Contributors(TypedDict):
	developers: list[Contributor]
	translators: list[Contributor]


def load_contributors(e: FileModifiedEvent | None = None) -> Contributors:
	with open("src/data/contributors.yml", "r") as f:
		raw_contribs = full_load(f)
	return Contributors(
		developers=[
			Contributor(
				c["name"],
				c["country"] if "country" in c else None,
				Snowflake(c["discord_id"]) if "discord_id" in c else None,
				c["roles"] if "roles" in c else [],
				c["links"] if "links" in c else [],
			)
			if not isinstance(c, str)
			else Contributor(c)
			for c in raw_contribs["developers"]
		],
		translators=[
			Contributor(
				c["name"],
				c["country"] if "country" in c else None,
				Snowflake(c["discord_id"]) if "discord_id" in c else None,
				c["roles"] if "roles" in c else [],
				c["links"] if "links" in c else [],
			)
			for c in raw_contribs["translators"]
		],
	)


contributors: Contributors = load_contributors()
subscribe(all_of(filter_path("src/data/contributors"), filter_file_suffix((".yml"))), load_contributors)


class AboutCommand(Extension):
	@slash_command(description="About the bot (ping, stats)")
	@slash_option(
		description="Whether you want the response to be visible for others in the channel",
		name="public",
		opt_type=OptionType.BOOLEAN,
	)
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def about(self, ctx: SlashContext, public: bool = False):
		loc = Localization(ctx)
		stats_loc = Localization(ctx, prefix="commands.info.about")
		_content = await locale_format(stats_loc, stats_loc.get("loading"))

		start_time = datetime.now(timezone.utc)
		loading_message = await fancy_message(ctx, _content, ephemeral=not public)

		reception_latency = start_time - datetime.fromtimestamp(ctx.id.created_at.timestamp(), tz=timezone.utc)

		reply_latency = datetime.fromtimestamp(loading_message.created_at.timestamp(), tz=timezone.utc) - start_time

		buttons: list[Button] = [
			Button(
				custom_id="about_contributors",
				label=stats_loc.get("buttons.contributors"),
				style=ButtonStyle.BLURPLE,
			)
		]
		strbuttons: list[str] = []
		processed_lines: list[str] = []
		_first_processed: bool = False
		if ctx.client.app.description:
			for line in ctx.client.app.description.splitlines():
				try:
					if ": http" in line or ":http" in line:
						name, url = line.split(":", 1)
						name = name.strip()

						loc_name = await locale_format(stats_loc, stats_loc.get(f"buttons['{name.lower()}']"))
						if not loc_name.startswith("`"):
							name = loc_name

						if len(buttons) < 25:
							buttons.append(Button(style=ButtonStyle.LINK, label=name, url=url.strip()))
						else:
							strbuttons.append(f"[{name}]({url})")
					else:
						if not _first_processed:
							_first_processed = True
							original_lines = list(
								await locale_format(
									source_loc, Localization(prefix=stats_loc.prefix).get("mes", typecheck=tuple)
								)
							)
							translated_lines = list(
								await locale_format(stats_loc, stats_loc.get("mes", typecheck=tuple))
							)
							index = original_lines.index(line)
							line = translated_lines[index]
						processed_lines.append(line)
				except ValueError:
					processed_lines.append(line)

		processed_description = "\n".join(processed_lines)

		if len(strbuttons) != 0:
			processed_description += "\n" + (" · ".join(strbuttons))
		sys_stats = get_stats()
		version = get_version()
		embed = Embed(description=processed_description, color=Colors.DEFAULT)  # fixme: no way to see owners now
		embed.add_fields(
			EmbedField(
				name=await locale_format(stats_loc, stats_loc.get("fields.avg_ping.name")),
				value=await locale_format(
					stats_loc, stats_loc.get("generic_values.time"), sec=fnum(ctx.client.latency, ctx.locale)
				),
				inline=True,
			),
			EmbedField(
				name=await locale_format(stats_loc, stats_loc.get("fields.latency.name")),
				value=f"{await locale_format(stats_loc, stats_loc.get('generic_values.time'), sec=fnum(reception_latency.microseconds / 1e6, ctx.locale))} / {await locale_format(stats_loc, stats_loc.get('generic_values.time'), sec=fnum(reply_latency.microseconds / 1e6, ctx.locale))}",
				inline=True,
			),
			EmbedField(
				await locale_format(stats_loc, stats_loc.get("fields.uptime.name")),
				ftime(datetime.now() - ctx.client.start_time, ctx.locale),
				inline=True,
			),
			EmbedField(
				name=await locale_format(stats_loc, stats_loc.get("fields.server_count.name")),
				value=str(ctx.client.guild_count),
				inline=True,
			),
			EmbedField(
				name=await locale_format(stats_loc, stats_loc.get("fields.load.name")),
				value=await locale_format(
					loc,
					stats_loc.get("fields.load.value"),
					cpu_load=sys_stats.cpu / 100,
					mem_load=sys_stats.ram / 100,
				),
				inline=True,
			),
			EmbedField(
				name=await locale_format(stats_loc, stats_loc.get("fields.version.name")),
				value=await locale_format(
					loc,
					stats_loc.get("fields.version.value"),
					version_type="tag" if version.tag else "commit",
					tag=version.tag,
					commit_hash=version.commit,
					last_updated_at=version.last_updated_at,
				),
				inline=True,
			),
			EmbedField(
				await locale_format(stats_loc, stats_loc.get("fields.host.name")),
				f"{platform.system()} {platform.release()} ({platform.architecture()[0]})",
				inline=True,
			),
		)
		# embed.add_field(await locale_format(stats_loc, stats_loc.get("fields.user_installs.name")), len(ctx.client.app.users))  # NONEXISTENT  # noqa: ERA001
		rows = []
		for i in range(0, len(buttons), 5):
			rows.append(ActionRow(*buttons[i : i + 5]))
		return await ctx.edit(embeds=[embed], components=rows)

	@component_callback("about_contributors")
	async def handle_contributors_button(self, ctx: ComponentContext):
		asyncio.create_task(ctx.defer(ephemeral=True))
		loc = Localization(ctx, prefix="commands.info.about.contributors")

		components = []
		components.append(TextDisplayComponent(content=loc.get("categories.developers")))
		components.extend([await contributor.render(loc) for contributor in contributors["developers"]])
		components.append(
			TextDisplayComponent(
				# TODO sort by country flag
				await locale_format(loc, loc.get("categories.translators"))
				+ f":\n{'\n'.join([await contributor.render(loc, simple=True) for contributor in contributors['translators']])}"
			)
		)
		await ctx.edit(components=ContainerComponent(*components, accent_color=Colors.DEFAULT))
