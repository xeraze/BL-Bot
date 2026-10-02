import logging
import os
import traceback
from typing import Optional

import discord

from utils.i18n import get_lang, t

log = logging.getLogger("bl-bot")


def get_error_log_channel_id() -> Optional[int]:
    """Получить ID канала для логирования ошибок."""
    raw = os.getenv("ERROR_LOG_CHANNEL_ID", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


async def log_error(
    interaction: discord.Interaction,
    error: Exception,
    command_name: str,
    user_message: str,
) -> None:
    """
    Логирует ошибку в канал и отправляет пользователю простое сообщение.
    
    Args:
        interaction: Discord interaction
        error: Возникшее исключение
        command_name: Название команды
        user_message: Простое сообщение для пользователя
    """
    try:
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ {user_message}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {user_message}", ephemeral=True)
    except Exception as e:
        log.error(f"Ошибка при отправке сообщения пользователю: {e}")

    channel_id = get_error_log_channel_id()
    if not channel_id or not interaction.guild:
        log.error(f"Команда '{command_name}' вызвала ошибку: {error}", exc_info=error)
        return

    try:
        channel = interaction.guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            log.error(f"Канал логов ({channel_id}) не найден или не является текстовым")
            return

        lang = get_lang(interaction)
        user_name = getattr(
            interaction.user, "name", t(lang, "errlog.unknown_user")
        )
        user_id = getattr(interaction.user, "id", "N/A")
        channel_name = getattr(interaction.channel, "name", "DM") if interaction.channel else "DM"

        error_traceback = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        if len(error_traceback) > 1500:
            error_traceback = error_traceback[-1500:]

        embed = discord.Embed(
            title=t(lang, "errlog.title", command=command_name),
            description=(
                t(lang, "errlog.user", name=user_name, id=user_id)
                + "\n"
                + t(lang, "errlog.channel", channel=channel_name)
            ),
            color=discord.Color.red(),
        )

        embed.add_field(
            name=t(lang, "errlog.field"),
            value=f"```\n{error_traceback}\n```",
            inline=False,
        )

        embed.set_footer(text=t(lang, "errlog.footer", command=command_name))

        await channel.send(embed=embed)
        log.error(
            f"Ошибка в команде '{command_name}' (пользователь {user_name}, ID {user_id}): {error}",
            exc_info=error,
        )

    except Exception as e:
        log.error(f"Ошибка при логировании в канал: {e}", exc_info=e)