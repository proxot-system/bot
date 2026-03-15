# Textbox Documentation

## Commands

You can use special commmands mid-sentence to do various stuff (like changing the facepic or coloring text), using `\c[arguments]` syntax (you can omit [] if there's no arguments). This is an almost direct copy of how [OneShot Textbox Maker](https://github.com/Leo40Git/OneShot-Textbox-Maker/) does this, check that project out if you want (even though it's archived), it's a java program that lets you make dialogues like the command in this bot too.<br/>

> `name` - Description - `example`

> ### `@` - Change facepic - `\@[OneShot/Niko/af]`
>
> This accepts three arguments separated by a colon (`:`)
>
> 1. the path for the facepic. you can find all of these [in this file](https://github.com/proxot-system/bot/blob/main/src/data/facepics.yml) (they are listed in '`name`: `discord emoji id` # `credits`' layout), or by using the facepic selector in the textbox dialogue builder using the bot. When writing the paths manually, make sure to not put "characters" or "faces" in the paths.
>
> - optional string
>
> 2. the transformation to apply to the image **(not implemented yet)**
>
> - optional string
>
> 3. the position for the face in the textbox **(not implemented yet)**
>
> - optional string
>
> If you start the frame text with an empty facepic: `\@[]` - it will force-disable the check which does the initial pad of the whole text on the side, if there is ANY facepic present in the frame. (useful if you want to overlay the facepic after the text was written? this only applies to the people who use multiple facepics in one frame, or move it around in the text)

> ### `n` - Line break - `\n`
>
> Self explanatory (probably shouldn't be included, but it's a command nonetheless)

## Raw file editing (.tbb)

This is a generic text file that has the entire State (all the dialogue frames and everything) saved inside it. It's usually outputted right above the preview for a frame, you can use this to export/import a dialogue you've made, or edit it in a text editor of your preference instead of using Discord.

### Parsing

The file is parsed line by line. The parser first looks for the `#> StateOptions <#` marker to know that the following lines are for [`StateOptions`](#stateoptions). It then looks for the `#> Frames <#` marker, after which it parses the lines for [`Frames`](#frames). Any lines starting with `#` or that are empty are ignored.

### `StateOptions`:

A newline separated list of key=value pairs. All of them can be omitted, the default value will be used instead

> `filetype` # Output filetype
>
> - text, one of WEBP, GIF, APNG, PNG, JPEG (default: "WEBP")
>   APNG: this sends it as a file without a filename, because Discord breaks them upon upload for some reason

> `send_to` # Whether to send the output to the channel or dms
>
> - number, one of: 1, 2, 3 (default: 1)
>   1. Doesn't send anywhere, replies to the textbox in an ephemeral message
>   2. Sends in Direct Messages of runner
>   3. Sends to the current channel. If the bot isn't in the server - the bot tries to followup with a normal message (runner needs External Apps in order for this to actually send the message)

> `force_send` # Whether to ignore checks before sending (e.g. no facepic being set or no text being set)
>
> - boolean true/false (default: false)

> `quality` # Quality
>
> - number, range: 1..=100 (default: 100)

### `Frames`:

A newline separated list of frames. Each frame has an options and text field, separated by a semicolon, options are wrapped in braces for ease of editing ({options};text).

#### `options`

> 1. `animated` # Whether the text should be animated
>
> - boolean, true/false (default: true)

> 2. `end_delay` # How many milliseconds to wait before showing the end arrow
>
> - number, range: 1.. (default: 150)

> 3. `end_arrow_bounces` # How many bounces should the end arrow make
>
> - number, range: 1.. (default: 4)

> 4. `end_arrow_delay` # How many milliseconds to wait between arrow bounces
>
> - number, range: 1.. (default: 150)

#### `text`

Text content for the frame (this supports [commands](#commands)). Whenever this overflows to the bottom of the textbox, it will move the text up with an animation, if you happen to be generating a static image file - it will cut off the beginning of the text.

### Example

```
#> StateOptions <#
force_send=True
send_to=3
#> Frames <#
{True;150;4;150;;};\\@[OneShot (fan)/Nikonlanger/Smug]Meow :3
```

# Variables

[Locations](#L88) (`SupportedLocations`): "aleft", "acenter", "aright", "left", "center", "right", "bleft", "bcenter", "bright"

> a - above
> b - below

```

```
