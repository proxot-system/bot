# type:ignore
import asyncio
import random
import time
import uuid
from urllib import parse

import aiohttp
import lavalink
from interactions import *
from interactions.api.events import *
from interactions_lavalink import Lavalink, Player
from interactions_lavalink.events import TrackException, TrackStart

from utilities.config import get_config
from utilities.emojis import emojis
from utilities.localization.localization import Localization, lformat
from utilities.message_decorations import *
from utilities.music.music_loaders import CustomSearch

# Utilities
from utilities.music.spotify_api import Spotify

spotify_creds: dict = get_config("music.spotify", typecheck=dict)
spotify = Spotify(client_id=spotify_creds["id"], secret=spotify_creds["secret"])


async def get_lavalink_stats():
	return {
		"playing_players": "placeholder",
		"played_time": "placeholder",
		"played_songs": "placeholder",
	}


class MusicCommands(Extension):
	# Base Command
	@slash_command(description="Listen to music using The World Machine!")
	@integration_types(guild=True, user=False)
	@contexts(bot_dm=False)
	async def music(self, ctx: SlashContext):
		pass

	def __init__(self, client):
		self.client = client
		self.lavalink: Lavalink = Lavalink(self.client)

		self.assign_node()

	def assign_node(self):
		node_information: dict = get_config("music.lavalink", typecheck=dict)

		if self.lavalink is None:
			assert "Unable to grab Lavalink Object."

		node = self.lavalink.add_node(
			node_information["ip"],
			node_information["port"],
			node_information["password"],
			"eu",
		)
		if node:
			print(f'Lavalink node "{node.name}" inititalized')
		self.lavalink.client.register_source(CustomSearch())

	async def get_playing_embed(self, player_status: str, player: Player, allowed_control: bool):
		track: lavalink.AudioTrack = player.current

		if track is None:
			return

		progress_bar_length = 10

		progress_bar = make_progress_bar(player.position, track.duration, progress_bar_length, "square")

		time = lavalink.parse_time(player.position)

		current = lavalink.format_time(player.position)
		total = lavalink.format_time(track.duration)

		description = f"From **{track.author}**\n\n{current} {emojis['icons']['sun']} {total}\n{progress_bar}\n\n"

		embed = Embed(
			title=track.title,
			description=description,
			url=track.uri,
			color=Colors.DEFAULT,
		)
		embed.set_author(name=player_status)
		embed.set_thumbnail(self.get_cover_image(track.identifier))

		requester = await self.client.fetch_user(track.requester)

		control_text = "Everyone can control" if allowed_control else "Currently has control"
		embed.set_footer(
			text=f"Requested by {requester.username}  ●  {control_text}",
			icon_url=requester.avatar_url,
		)

		return embed

	async def get_queue_embed(self, player: Player, page: int):
		queue_list = []

		queue = player.queue[(page * 10) - 10 : (page * 10)]
		i = (page * 10) - 9

		if player.current is None:
			return Embed(
				description="[ There are no tracks in the player! ]",
				color=Colors.DEFAULT,
			)

		for song in queue:
			title = song.title
			author = song.author
			requester = song.requester

			user = await self.client.fetch_user(requester)

			queue_list.append(
				EmbedField(
					name=f"{i}. {title}",
					value=f"*by {author}* - Requested by {user.mention}",
					inline=False,
				)
			)

			i += 1

		track = player.current
		guild = await self.client.fetch_guild(player.guild_id)

		time = 0

		for t in player.queue:
			time = time + t.duration / 1000

		hours = int(time / 3600)
		minutes = int(hours / 60)

		description = f"### Currently Playing:\n**{track.title}** from **{track.author}** {emojis['icons']['sun']}\n\n*There are currently* ***{len(player.queue)}*** *songs in the queue.*\n*Approximately* ***{hours} hours*** and ***{minutes} minutes*** *left.*\n### Next Up..."

		queue_embed = Embed(description=description, color=Colors.DEFAULT)

		queue_embed.set_author(name=f"Queue for {guild.name}", icon_url=guild.icon.url)
		queue_embed.set_thumbnail(url=self.get_cover_image(track.identifier))
		queue_embed.set_footer(
			text="Use /music_queue remove to remove a track.\nUse /music_queue jump to jump to a track."
		)
		queue_embed.fields = queue_list

		return queue_embed

	async def can_modify(self, track_author: int, author: Member, guild_id: Snowflake):
		track_author_member: Member = await self.client.fetch_member(track_author, guild_id)

		if Permissions.MANAGE_CHANNELS in author.guild_permissions:
			return True

		if not track_author_member.voice or not track_author_member.voice.channel:
			return True

		if int(author.id) == track_author:
			return True

		return False

	player_user_cooldown = {}

	async def on_cooldown(self, author: Member):
		if Permissions.MANAGE_CHANNELS in author.guild_permissions:
			return False

		cooldown_time = self.player_user_cooldown.get(author.id, 0)

		if cooldown_time > time.time():
			return True

		self.player_user_cooldown[author.id] = time.time() + 30

		return False

	@music.subcommand(sub_cmd_description="Play a song!")
	@slash_option(
		name="song",
		description="Input a search term, or paste a link",
		opt_type=OptionType.STRING,
		required=True,
		autocomplete=True,
	)
	async def play(self, ctx: SlashContext, song: str):
		loc = Localization(ctx, prefix="commands.music.commands.play")
		# Getting user's voice state
		voice_state = ctx.member.voice
		if not voice_state or not voice_state.channel:
			return await fancy_message(
				ctx,
				"[ You're not connected to a voice channel. ]",
				color=Colors.BAD,
				ephemeral=True,
			)

		player = None
		tries = 0

		# Connecting to voice channel and getting player instance
		while player is None:
			try:
				player = await self.lavalink.connect(voice_state.guild.id, voice_state.channel.id)
			except:
				if tries > 2:
					return await fancy_message(
						ctx,
						"[ An error has occurred, please try again later. ]",
						color=Colors.BAD,
					)

				self.assign_node()
				tries += 1

		message = await fancy_message(ctx, await lformat(loc, loc.l("loading.search")))

		result = await self.lavalink.client.get_tracks(song, check_local=True)
		tracks = result.tracks

		if len(tracks) == 0:
			return await fancy_message(message, "[ No results found. ]", edit=True, color=Colors.BAD)

		player.store("Channel", ctx.channel)
		player.store("Message", message)

		[player.add(track, requester=int(ctx.author.id)) for track in tracks]

		if player.is_playing:
			add_to_queue_embed = self.added_to_playlist_embed(ctx, player, tracks[0])
			return await message.edit(embeds=add_to_queue_embed)
		else:
			try:
				await player.play()
			except:
				self.assign_node()
				await player.play()

	def added_to_playlist_embed(self, ctx: SlashContext, player: Player, track: lavalink.AudioTrack):
		add_to_queue_embed = Embed(
			title=track.title,
			url=track.uri,
			description=f"From **{track.author}** was added to the queue",
			color=Colors.GREEN,
		)

		add_to_queue_embed.set_author(name=f"Requested by {ctx.member.username}", icon_url=ctx.member.avatar.url)

		add_to_queue_embed.set_thumbnail(self.get_cover_image(track.identifier))
		add_to_queue_embed.set_footer(
			text="Was this a mistake? You can use[ /music remove position:-1 mine:True ] to remove your last song."
		)

		return add_to_queue_embed

	@music.subcommand(sub_cmd_description="Play a file!")
	@slash_option(
		name="file",
		description="Input a file to play",
		opt_type=OptionType.ATTACHMENT,
		required=True,
	)
	async def file(self, ctx: SlashContext, file: Attachment):
		loc = Localization(ctx, prefix="commands.music.commands.file")
		# Getting user's voice state
		voice_state = ctx.member.voice

		if not voice_state or not voice_state.channel:
			return await fancy_message(
				ctx,
				"[ You're not connected to a voice channel. ]",
				color=Colors.BAD,
				ephemeral=True,
			)

		message = await fancy_message(ctx, await lformat(loc, loc.l("loading.file")))

		player = await self.lavalink.connect(voice_state.guild.id, voice_state.channel.id)

		fetched_tracks: list[lavalink.AudioTrack] = await player.get_tracks(file.url)

		if len(fetched_tracks) == 0:
			return await fancy_message(
				ctx,
				"[ Attachment must either be a video or audio file. ]",
				color=Colors.BAD,
				ephemeral=True,
			)

		track: lavalink.AudioTrack = fetched_tracks[0]

		track.title = file.filename
		track.uri = file.url
		track.identifier = file.url
		track.author = "Uploaded File"
		track.requester = int(ctx.author.id)

		player.add(track)

		player.store("Channel", ctx.channel)

		await message.delete()

		if player.is_playing:
			add_to_queue_embed = self.added_to_playlist_embed(ctx, player, track)

			return await ctx.channel.send(embeds=add_to_queue_embed)

		await player.play()

	@music.subcommand(sub_cmd_description="Stop the music!")
	async def stop(self, ctx: SlashContext):
		player: Player = self.lavalink.get_player(ctx.guild_id)

		if player is None:
			return await fancy_message(
				ctx,
				"[ Player not found, try putting on some music! ]",
				color=Colors.BAD,
				ephemeral=True,
			)

		player.current = None
		await self.lavalink.disconnect(ctx.guild_id)

		await ctx.send(f"[ {ctx.author.mention} has stopped the player. ]")

	@music.subcommand(sub_cmd_description="Go to a specific song in the queue!")
	@slash_option(
		name="position",
		description="Which song to jump to",
		opt_type=OptionType.INTEGER,
		required=True,
	)
	async def jump(self, ctx: SlashContext, position: int):
		if await self.on_cooldown(ctx.author):
			return await fancy_message(ctx, "[ You are on cooldown! ]", color=Colors.BAD, ephemeral=True)

		voice_state = ctx.member.voice
		if not voice_state or not voice_state.channel:
			return await fancy_message(
				ctx,
				"[ You're not connected to a voice channel. ]",
				color=Colors.BAD,
				ephemeral=True,
			)

		player: Player = self.lavalink.get_player(ctx.guild_id)

		if player is None:
			return await fancy_message(
				ctx,
				"[ Player not found, try putting on some music! ]",
				color=Colors.BAD,
				ephemeral=True,
			)

		if len(player.queue) == 0:
			return await fancy_message(ctx, "[ Queue is empty! ]", color=Colors.BAD, ephemeral=True)

		if position > len(player.queue) or position < 0:
			return await fancy_message(ctx, "[ Invalid position! ]", color=Colors.BAD, ephemeral=True)

		song = player.queue[position]

		if player.loop != 2:
			del player.queue[:position]
		else:
			del player.queue[position]
			player.queue.insert(0, song)

		await player.skip()

		await ctx.send(f"[ {ctx.user.mention} jumped to **{song.title}**! ]")

	@music.subcommand(sub_cmd_description="Remove a song from the queue.")
	@slash_option(
		name="position",
		description="The position of the song you want to remove",
		opt_type=OptionType.INTEGER,
	)
	@slash_option(
		name="mine",
		description="Whether you want to browse only your songs",
		opt_type=OptionType.BOOLEAN,
		argument_name="own",
	)
	async def remove(self, ctx: SlashContext, position: int = -1, own: bool = False):
		voice_state = ctx.member.voice
		if not voice_state or not voice_state.channel:
			return await fancy_message(
				ctx,
				"[ You're not connected to a voice channel. ]",
				color=Colors.BAD,
				ephemeral=True,
			)

		player: Player = self.lavalink.get_player(ctx.guild_id)

		if player is None:
			return await fancy_message(
				ctx,
				"[ Player not found, start playing some music first! ]",
				color=Colors.BAD,
				ephemeral=True,
			)
		queue = player.queue
		if len(queue) == 0:
			return await fancy_message(ctx, "[ The queue is empty! ]", color=Colors.WARN, ephemeral=True)
		if own and any(track.requester == int(ctx.user.id) for track in queue):
			return await fancy_message(
				ctx,
				"[ You haven't queued any songs yet! ]",
				color=Colors.WARN,
				ephemeral=True,
			)
		if position < 0:
			position = -position
			queue = queue[::-1]  # reverses the queue
		if position == 0:
			position = 1
		for index, track in enumerate(queue):
			if own and track.requester != int(ctx.user.id):
				continue

			if position == index + 1:
				if not self.can_modify(track.requester, ctx.author, ctx.guild_id):
					return await fancy_message(
						ctx,
						"[ You can't remove this song. ]",
						color=Colors.BAD,
						ephemeral=True,
					)

			song = track
			del queue[index]
			return await ctx.send(f"[ {ctx.user.mention} removed **{song.title}** from the queue. ]")

		return await fancy_message(
			ctx,
			f"[ Invalid position or no matching song found. The queue length is {len(queue)}! ]",
			color=Colors.BAD,
			ephemeral=True,
		)

	@music.subcommand(sub_cmd_description="Remove the most recent song from the queue added by you.")
	async def remove_last(self, ctx: SlashContext):
		player = self.lavalink.get_player(ctx.guild_id)

		if not player:
			return await fancy_message(
				ctx,
				"[ An error occurred, please try again later. ]",
				ephemeral=True,
				color=Colors.BAD,
			)

		queue = player.queue[::-1]

		for track in queue:
			if track.requester == int(ctx.user.id):
				player.queue.remove(track)
				return await ctx.send(f"[ {ctx.user.mention} removed **{track.title}** from the queue. ]")

	@remove.autocomplete("position")
	async def autocomplete_remove(self, ctx: AutocompleteContext):
		input_text = ctx.input_text
		player: Player = self.lavalink.get_player(ctx.guild_id)

		if player is None:
			return await ctx.send([])

		show_first_results = False

		if input_text == "":
			show_first_results = True

		queue = []

		for i, item in enumerate(player.queue):
			queue.append(f"{i + 1}. {item.title}")

		choices = []

		for i, item in enumerate(queue):
			if show_first_results:
				choices.append({"name": item, "value": i})
			else:
				if input_text.lower() in item.lower():
					choices.append({"name": item, "value": i})

		if len(choices) > 24:
			choices = choices[:24]

		await ctx.send(choices)

	@jump.autocomplete("position")
	async def autocomplete_jump(self, ctx: AutocompleteContext):
		input_text = ctx.input_text
		player: Player = self.lavalink.get_player(ctx.guild_id)

		if player is None:
			return await ctx.send([])

		show_first_results = False

		if input_text == "":
			show_first_results = True

		queue = []

		for i, item in enumerate(player.queue):
			queue.append(f"{i + 1}. {item.title}")

		choices = []

		for i, item in enumerate(queue):
			if show_first_results:
				choices.append({"name": item, "value": i})
			else:
				if input_text.lower() in item.lower():
					choices.append({"name": item, "value": i})

		if len(choices) > 24:
			choices = choices[:24]

		await ctx.send(choices)

	async def load_spotify_search(self, content):
		search_: dict = await spotify.search(content, limit=25, type="track")

		if search_ == "error":
			return [
				{
					"Text": "An error occurred within the search",
					"URL": "ef9hur39fh3ehgurifjehiie",
				}
			]

		tracks = []

		for result in search_["tracks"]["items"]:
			song_name = result["name"]
			artists = result["artists"][0]
			url = result["id"]

			if len(f'"{song_name}"\n - {artists["name"]}') > 99:
				continue

			tracks.append(
				{
					"Text": f'"{song_name}"\n by {artists["name"]}',
					"URL": f"http://open.spotify.com/track/{url}",
				}
			)

		return tracks

	@play.autocomplete("song")
	async def autocomplete(self, ctx: AutocompleteContext):
		text = ctx.input_text

		if text == "":
			text = "Oneshot by nightmargin"

		raw_text = text

		if len(text) > 25:
			text = text[:25]

		items = await self.load_spotify_search(text)

		if "https://youtu.be" in text or "https://www.youtube.com" in text or "https://m.youtube.com" in text:
			choices = [{"name": "🔗 Youtube URL", "value": raw_text}]
		elif "http://open.spotify.com/" in text or "https://open.spotify.com/" in text:
			choices = [{"name": "🔗 Spotify URL", "value": raw_text}]
		elif "https://soundcloud.com" in text:
			choices = [{"name": "🔗 Soundcloud URL", "value": raw_text}]
		else:
			choices = [{"name": item["Text"], "value": item["URL"]} for item in items]

		try:
			await ctx.send(choices)
		except:
			pass

	@listen()
	async def on_track_start(self, event: TrackStart):
		player: Player = event.player

		channel: GuildText = player.fetch("Channel")

		await self.on_player(event.player, channel)

	@listen()
	async def on_track_error(self, event: TrackException):
		player: Player = event.player

		message: Message = player.fetch("Message")
		player.store("Error", True)

		embed = Embed(
			title="An error occurred when playing this track",
			description=f"Please try again later",
			color=Colors.RED,
		)

		print(f'Error occurred when playing a track. "{event.message}"')

		await message.edit(content=emojis["icons"]["sleep"], embed=embed, components=[])

	@listen()
	async def voice_state_update(self, event: VoiceUserLeave):
		player: Player = self.lavalink.get_player(event.channel.guild.id)

		if player is None:
			return

		if event.author.bot:
			return

		channel = event.channel

		if not channel.id == player.channel_id:
			return

		if len(channel.voice_members) <= 2:
			text_channel = player.fetch("Channel")

			await fancy_message(
				text_channel,
				f"[ Everyone has disconnected from {channel.mention}. To stop playing music, please use ``/music stop``. ]",
			)

	@staticmethod
	def get_buttons():
		return [
			Button(
				style=ButtonStyle.RED,
				emoji=PartialEmoji(id=1019286929059086418),
				custom_id="queue",
				label="Open Queue",
			),
			Button(
				style=ButtonStyle.RED,
				emoji=PartialEmoji(id=1019286926404091914),
				custom_id="loop",
				label="Loop Track",
			),
			Button(
				style=ButtonStyle.RED,
				emoji=PartialEmoji(id=1019286927888883802),
				custom_id="playpause",
				label="Pause",
			),
			Button(
				style=ButtonStyle.RED,
				emoji=PartialEmoji(id=1019286930296410133),
				custom_id="skip",
				label="Skip",
			),
		]

	@staticmethod
	async def get_queue_buttons():
		options = [
			Button(
				style=ButtonStyle.RED,
				emoji=PartialEmoji(id=1031309494946385920),
				custom_id="left",
			),
			Button(
				style=ButtonStyle.BLUE,
				emoji=PartialEmoji(id=1031309497706225814),
				custom_id="shuffle",
				label="Shuffle Queue",
			),
			Button(
				style=ButtonStyle.GREY,
				emoji=PartialEmoji(id=1019286926404091914),
				custom_id="loopqueue",
				label="Loop Queue",
			),
			Button(
				style=ButtonStyle.RED,
				emoji=PartialEmoji(id=1031309496401793064),
				custom_id="right",
			),
		]

		return options

	@music.subcommand()
	async def get_lyrics(self, ctx: SlashContext):
		"""Get the lyrics of the current song playing."""

		await ctx.defer(ephemeral=True)

		player = self.lavalink.get_player(ctx.guild_id)

		if player is None or player.current is None:
			return await fancy_message(ctx, "[ No tracks are currently playing! ]", ephemeral=True)

		track = player.current

		parsed_title = parse.quote(f"{track.title} {track.author}")

		api_url = f"https://some-random-api.com/lyrics?title={parsed_title}"

		async with aiohttp.ClientSession() as lyricsSession:
			async with lyricsSession.get(api_url) as jsondata:
				lyric_data: dict = await jsondata.json()

		if "error" in lyric_data.keys():
			return await ctx.send(
				embed=Embed(
					title=f"{track.title} Lyrics",
					description="`[ No Lyrics found. ]`",
					color=Colors.BAD,
				)
			)

		lyrics = lyric_data["lyrics"]

		if len(lyrics) > 4080:
			song = f"{lyric_data[:2080]}...\n\nGet the full lyrics [here.]({lyrics.url})"

		return await ctx.send(
			embed=Embed(
				title=f"{track.title} Lyrics",
				description=f"```{lyrics}```",
				color=Colors.DEFAULT,
				footer=EmbedFooter(text=f"Lyrics provided by Some Random API"),
			)
		)

	@music.subcommand()
	async def fetch_player(self, ctx: SlashContext):
		"""Get the player."""

		player = self.lavalink.get_player(ctx.guild_id)

		if player is None or player.current is None:
			return await fancy_message(ctx, "[ No tracks are currently playing! ]", ephemeral=True)

		await fancy_message(ctx, "[ Player should open momentarily. ]", ephemeral=True)

		await self.on_player(player, ctx.channel)

	async def on_player(self, player: Player, channel: GuildText):
		if player.loop == 1:
			return

		player_uid = str(uuid.uuid4())

		player.store("uid", player_uid)
		message: Message = player.fetch("Message")

		main_buttons = self.get_buttons()

		niko = emojis["icons"]["jam"]
		player_state = "Now Playing..."
		embed = await self.get_playing_embed(player_state, player, True)
		if message:
			message = await message.edit(content=niko, embed=embed, components=main_buttons)

		stopped_track = player.current

		while player.current is not None and player_uid == player.fetch("uid"):
			if player.paused:
				player_state = "Paused"
				niko = emojis["icons"]["sleep"]
				main_buttons[2].label = "Resume"
				main_buttons[2].style = ButtonStyle.BLUE
			else:
				player_state = "Now Playing..."
				niko = emojis["icons"]["jam"]
				main_buttons[2].label = "Pause"
				main_buttons[2].style = ButtonStyle.RED

			if player.loop == 1:
				player_state = "Now Looping..."
				main_buttons[1].label = "Stop Looping"
				main_buttons[1].style = ButtonStyle.BLUE
			else:
				main_buttons[1].label = "Loop Track"
				main_buttons[1].style = ButtonStyle.RED

			user = await self.client.fetch_member(player.current.requester, player.guild_id)

			can_control: bool = False

			voice_state = user.voice
			if not voice_state or not voice_state.channel:
				can_control = True

			embed = await self.get_playing_embed(player_state, player, can_control)

			if message:
				message = await message.edit(content=niko, embed=embed, components=main_buttons)

			await asyncio.sleep(1)

		if player.fetch("Error"):
			return

		if stopped_track is None:
			embed = Embed(
				title="An error occurred when playing this track",
				description=f"Please try again later",
				color=Colors.RED,
			)

			embed.set_author(name="Stopped Playing...")

		else:
			embed = Embed(
				title=stopped_track.title,
				url=stopped_track.uri,
				description=f"From **{stopped_track.author}**",
				color=Colors.GRAY,
			)

			embed.set_author(name="Stopped Playing...")
			embed.set_thumbnail(self.get_cover_image(stopped_track.identifier))

			requester = await self.client.fetch_user(stopped_track.requester)
			embed.set_footer(text="Requested by " + requester.username, icon_url=requester.avatar_url)

		message = await message.edit(content=emojis["icons"]["sleep"], embed=embed, components=[])

	@component_callback("queue", "loop", "playpause", "skip", "lyrics")
	async def buttons(self, ctx: ComponentContext):
		player: Player = self.lavalink.get_player(ctx.guild_id)

		if player is None:
			return

		if ctx.custom_id == "queue":
			player.store("current_page", 1)

			if len(player.queue) < 1:
				return await fancy_message(
					ctx,
					"[ No songs in queue, use ``/music play`` to add some! ]",
					ephemeral=True,
					color=Colors.BAD,
				)

			embed = await self.get_queue_embed(player, 1)

			components = await self.get_queue_buttons()
			return await ctx.send(embed=embed, components=components, ephemeral=True)

		if ctx.custom_id == "lyrics":
			message = await fancy_message(ctx, f"[ Searching Lyrics for this track... ]", ephemeral=True)
			embed = await self.get_lyrics(player.current)
			return await ctx.edit(message, embed=embed)

		if not await self.can_modify(player.current.requester, ctx.author, ctx.guild.id):
			return await fancy_message(
				ctx,
				"[ You cannot modify the player. ]",
				ephemeral=True,
				color=Colors.RED,
			)

		await ctx.defer(edit_origin=True)

		async def send_update(str):
			return await ctx.channel.send(str, allowed_mentions={"users": []})

		match ctx.custom_id:
			case "loop":
				if not player.loop:
					player.set_loop(1)
					return await send_update(f"[ {ctx.author.mention} Started Looping. ]")
				else:
					player.set_loop(0)
					return await send_update(f"[ {ctx.author.mention} Stopped Looping. ]")

			case "playpause":
				await player.set_pause(not player.paused)

				if player.paused:
					return await send_update(f"[ {ctx.author.mention} Paused. ]")
				else:
					return await send_update(f"[ {ctx.author.mention} Resumed. ]")

			case "skip":
				player.set_loop(0)

				await player.skip()

				return await send_update(f"[ {ctx.author.mention} Skipped. ]")

	@component_callback("shuffle", "loopqueue", "left", "right")
	async def queue_buttons(self, ctx: ComponentContext):
		player: Player = self.lavalink.get_player(ctx.guild_id)

		page = player.fetch("current_page")

		if ctx.custom_id == "left":
			if page == 1:
				page = 1
			else:
				page -= 1

		max_pages = (len(player.queue) + 9) // 10

		if ctx.custom_id == "right":
			if page < max_pages:  # Only allow moving to the right if there are more pages to display
				page += 1

		player.store("current_page", page)

		message = None

		if ctx.custom_id == "shuffle":
			if await self.on_cooldown(ctx.author):
				return await fancy_message(ctx, "[ You are on cooldown! ]", color=Colors.BAD, ephemeral=True)

			random.shuffle(player.queue)
			message = await ctx.channel.send(f"[ {ctx.author.mention} Shuffled the Queue. ]")

		if ctx.custom_id == "loopqueue":
			if player.loop == 2:
				player.set_loop(0)
				message = await ctx.channel.send(f"[ {ctx.author.mention} Stopped Looping the Queue. ]")
			else:
				player.set_loop(2)
				message = await ctx.channel.send(f"[ {ctx.author.mention} is Looping the Queue. ]")

		embed = await self.get_queue_embed(player, page)

		components = await self.get_queue_buttons()
		await ctx.edit_origin(embed=embed, components=components)
		if message is not None:
			await asyncio.sleep(5)
			await message.delete()

	def get_cover_image(self, uid: str):
		if "https://i.scdn.co/" in uid:
			return uid
		else:
			return f"https://img.youtube.com/vi/{uid}/hqdefault.jpg"
