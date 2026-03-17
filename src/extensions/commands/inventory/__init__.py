from interactions import (
	Extension,
	SlashContext,
	contexts,
	integration_types,
	slash_command,
)

from .treasures import command as treasures_cmd


class InventoryCommands(Extension):
	@slash_command(
		name="inventory",
		description="Commands related to the player's inventory",
	)
	@integration_types(guild=True, user=True)
	@contexts(bot_dm=True)
	async def inventory(self, ctx: SlashContext): ...

	treasures = inventory.subcommand(
		sub_cmd_name="treasures",
		sub_cmd_description="View the treasures you have in your inventory (or see someone else's!)",
	)(treasures_cmd)
