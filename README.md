<div align="center">
    <img src="https://github.com/proxot-system.png" width="128" height="128">
</div>

# <div align="center"> Proxot System bot (The World Machine) </div>

<div align="center">

### A discord bot based off the videogame OneShot, and built using the `interactions-py` library.

For more information on what you can do with this bot, check out our [website](https://www.theworldmachine.xyz/invite).

</div>

## [Documentation](./md/en/Documentation.md)

## Contributing

### Localization

Localization is done on [the translation website](https://translate.theworldmachine.xyz/) (we are using [Weblate](https://translate.theworldmachine.xyz/about/)). You are required to register using a Google account for the time being, after that you may suggest any changes to the text in any language, for the Lead Translators of that language to review. Contact @meqativ on the community server if you wish to become a Lead Translator for any language.

> [!NOTE]
> Some basic rules for translating
>
> - We are not looking for AI/ML translations, please only translate if you are a native of the language & you're confident in your skills. Feel free to use AI as a tool though, just don't copy-paste stuff from it without checking (e.g. if you can't find a word you can detail the context and ask the ai for suggestions. i recommend https://aistudio.google.com since it can access the internet to look up stuff)
> - Make sure to use the same terms/wording as the OneShot game or the Discord app does in your language (when possible) so that it's familiar for all people (e.g. if Discord translated a "Stage" channel to -> "Етап" (ukrainian), make sure to do that in your translation too, even if it's a dumb translation by discord)
> - Follow [other common translator expectations](https://translate.wordpress.com/translator-expectations/#:~:text=Translator%20Best%20Practices)
> - If you are found sending spam/incorrect translations - you will be removed from the project without a possibility of returning

> [!NOTE]
> `/transmission` - **does not** have localizations yet

### Pull Requests

As with any other repo, pull requests and bug reporting is always welcomed.

### Crediting

Contributing in any way to the discord bot will have your name be put in the website's credits and a role assigned on the discord.

## Running your own instance

### Prerequisites

Make sure you have python 3.13.11 (u can easily install this one via `pyenv`, if you have `pyenv` already installed - step 1 will ask you to download the right version) and the `pipenv` module installed.

```sh
python -m pip install pipenv
```

Clone the repo to get the codebase downloaded on your device

```sh
git clone https://github.com/proxot-system/bot twm-bot && cd twm-bot && git clone https://github.com/proxot-system/i18n src/data/locales
```
> [!NOTE]
> If you want to pull both locales and the bot at the same time you can use this command:
> (you should be in the root directory of the bot, aka the twm-bot folder u just cloned)
> ```sh
> git pull && cd src/data/locales && git pull origin main && cd ../../../
> ```
### Step 1: Install Dependencies

```sh
pipenv install
```

### Step 2: Fill in configs

There is file called `bot-config.example.yml` which has example configurations, including the bot token, database endpoints and api keys. Rename or duplicate this file to `bot-config.yml` in the same folder and fill it in. <br>
A similar file is also located in the lavalink directory.

### Step 3: Running the bot

```sh
pipenv run bot
```
