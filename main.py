import asyncio
import logging
import os

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

from utils.error_handler import log_error
from utils.i18n import get_lang, t
from utils.permissions import MissingRoleError, RoleNotConfiguredError

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("bl-bot")

intents = discord.Intents.default()
intents.message_content = True


class BLCommandTree(app_commands.CommandTree):
    """Глобальный обработчик ошибок слэш-команд.

    discord.py вызывает ``tree.on_error`` для любой ``AppCommandError``
    (в том числе при проверках ролей), в отличие от несуществующего
    события ``on_app_command_error``.
    """

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
        /,
    ) -> None:
        command_name = interaction.command.name if interaction.command else "unknown"
        lang = get_lang(interaction)

        if isinstance(error, RoleNotConfiguredError):
            await log_error(
                interaction,
                error,
                command_name,
                t(lang, "err.not_configured"),
            )
            return

        if isinstance(error, MissingRoleError):
            await log_error(
                interaction,
                error,
                command_name,
                t(lang, "err.no_role"),
            )
            return

        if isinstance(error, app_commands.CheckFailure):
            await log_error(
                interaction,
                error,
                command_name,
                t(lang, "err.check_failed"),
            )
            return

        if isinstance(error, app_commands.MissingRequiredArgument):
            await log_error(
                interaction,
                error,
                command_name,
                t(lang, "err.missing_arg", name=error.param.name),
            )
            return

        if isinstance(error, app_commands.BadArgument):
            await log_error(
                interaction,
                error,
                command_name,
                t(lang, "err.bad_arg", error=str(error)),
            )
            return

        await log_error(
            interaction,
            error,
            command_name,
            t(lang, "err.generic"),
        )


class BLBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=intents, tree_cls=BLCommandTree)

    async def setup_hook(self) -> None:
        await self.load_extension("cogs.bl")
        await self.load_extension("cogs.reviews")

        guild_id = os.getenv("GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Слэш-команды синхронизированы для сервера %s", guild_id)
        else:
            await self.tree.sync()
            log.info("Слэш-команды синхронизированы глобально (может занять до часа)")

    async def on_ready(self) -> None:
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.competing,
                name="Broken Lens",
            )
        )
        log.info("Бот запущен как %s (ID: %s)", self.user, self.user.id)

async def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN не задан в .env")

    async with BLBot() as bot:
        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
