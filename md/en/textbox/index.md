# Textbox Documentation

## Commands

You can use special commands mid-sentence to do various stuff (like changing the facepic or coloring text), using `\c[arguments]` syntax (you can omit `[]` if there's no arguments). This is very heavily inspired by [OneShot Textbox Maker](https://github.com/Leo40Git/OneShot-Textbox-Maker/) does this

> `name` - Description - `example`

> ### `@` - Change facepic - `\@[OneShot/Niko/af]`
>
> This command changes the character portrait displayed on the right side of the textbox
>
> Accepts the path for the facepic as an argument. You can find these in the facepic selector or in [the source configuration here](../../../src/data/facepics.yml)
>
> **Padding Behavior:**
> - By default, if any `\@` command is present in the frame text, the entire frame's text will be padded to the left to make room for a facepic
> - `\@[]` or `\@[clear]`: These are aliases. They display an invisible facepic but **keep the text padded**. This is useful if you want a character to "disappear" but don't want the text to jump and change width
> - This behavior can be overridden using the `force_padding` [frame option](#options)

> ### `c` - Color text - `\c[#c386ff]` or `\c[red]`
>
> Changes the color of the text following the command. It uses a [CSS color parser](https://github.com/mazznoer/csscolorparser-rs?tab=readme-ov-file#relative-color), supporting hex codes (with alpha/transparency), RGB, and standard CSS color names
> - You can chain these to draw rainbows or multi-colored words (there are plans about making this more automatable)
> - Use `\c[]` to reset to the default white color

> ### `s` - Text speed - `\s[2.0]`
>
> Applies a modifier on the GIF frame delay. Default is `1.0` (no change), maximum is `50.0` (values higher than 25 already dont matter btw)

> ### `d` - Delay - `\d[500]`
>
> Inserts a pause frame that delays for that amount of milliseconds. This frame does not get affected by text speed

> ### `u` - Unicode character - `\u[#1F408]` or `\u[128008]`
>
> Injects a specific unicode character into the text using its hex (prefixed with `#`) or decimal code

> ### `n` - Line break - `\n`
>
> Forces the text to move to the next line

> ### `l` - Locale string - `\l[commands.info.about.mes[0]]`
>
> Injects a localization string from the bot's translation files based on the provided path (virtually useless)


## Raw file editing (.tbb)

This is a generic text file that has the entire State (all the dialogue frames and configuration) saved inside it. You can use this to export/import dialogues or edit them in an external text editor. It is always provided alongside the image preview of the textbox editor in the bot

### Parsing

The file is parsed line by line. The parser looks for the `#> StateOptions <#` marker for global settings and the `#> Frames <#` marker for dialogue content. Lines starting with `#` (outside of markers) or empty lines are ignored

### `StateOptions`:

A list of `key=value` pairs. Default values are used if a key is omitted

> `filetype` (default: WEBP)
> - \# Output filetype
> - Options: WEBP, GIF, APNG, PNG, JPEG
> - **note:** APNG files are sent without an extension to prevent Discord from stripping the animation

> `send_to` (default: 1)
> - \# Output destination (same as command argument)
> - 1: Ephemeral reply
> - 2: Direct Messages
> - 3: Current Channel

> `quality` (default: 100)
> - \# Rendering quality
> - Range: 1..100

> `loops` (default: 0)
> - \# Animation loops
> - 0: Normal infinitely looping animation
> - 1+: Specific number of plays

> `force_send` (default: False)
> - \# Bypass checks for the completeness of the frame before sending
> - boolean: True/False

> `frame_index` (default: 0)
> - # Initial frame focus
> - number: The frame number to show in the editor preview upon loading

### `Frames`:

A list of newline separated frames in the format `{options};text`. If you're editing this manually, remember to use [\n](#n---line-break---n) to separate text with newlines visually in the frame

#### `options`
This is a semicolon separated list of values, if you wish to fall back to the default of any value just don't include it (e.g. `{;;;;true};Meow` would overwrite only force_padding)
> 1. `animated` (default: True)
> - \# Toggle frame animation
> - boolean: True/False

> 2. `end_delay` (default: 150)
> - \# Wait time before the end arrow appears
> - number: milliseconds

> 3. `end_arrow_bounces` (default: 4)
> - \# Number of arrow animations
> - number: count

> 4. `end_arrow_delay` (default: 150)
> - \# Delay between arrow bounces
> - number: milliseconds

> 5. `force_padding` (default: None)
> - \# Explicitly control facepic padding
> - boolean: True (always pad), False (never pad), None (automatic based on `\@` command)

#### `text`

The actual dialogue content. This supports all [commands](#commands) listed above. When text overflows the bottom of the box, it will automatically scroll up 4 lines.

### Example

```
#> StateOptions <#
filetype=WEBP
send_to=1
quality=100
loops=0

#> Frames <#
{True;150;4;150;};\\@[OneShot/Niko/83c]Hello! \c[yellow]miaow meeeow meowmeow meow?\c[]
{True;150;4;150;False};\\@[OneShot/The World Machine/Speak]This text will overlap the facepic because force_padding is False.
```