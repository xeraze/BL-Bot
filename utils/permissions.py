import os

import discord
from discord import app_commands

_PLACEHOLDERS = {"", "0", "ROLE_ID_HERE", "your_role_id_here"}


class MissingRoleError(app_commands.CheckFailure):
    """Исключение для отсутствующей роли с информативным сообщением."""
    def __init__(self, role_id: int, env_key: str):
        self.role_id = role_id
        self.env_key = env_key
        super().__init__(f"У вас нет роли для этой команды (требуется роль {role_id})")


def _parse_role_id(env_key: str) -> int | None:
    raw = os.getenv(env_key, "").strip()
    if raw in _PLACEHOLDERS:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def has_role(env_key: str):
    """Проверка роли по ID из .env. Пустая заглушка = проверка отключена."""

    async def predicate(interaction: discord.Interaction) -> bool:
        role_id = _parse_role_id(env_key)
        if role_id is None:
            return True
        if interaction.guild is None:
            raise MissingRoleError(role_id, env_key)
        member = interaction.user
        if not isinstance(member, discord.Member):
            raise MissingRoleError(role_id, env_key)
        
        has_required_role = any(role.id == role_id for role in member.roles)
        if not has_required_role:
            raise MissingRoleError(role_id, env_key)
        return True

    return app_commands.check(predicate)


def member_has_role(member: discord.Member, env_key: str) -> bool:
    role_id = _parse_role_id(env_key)
    if role_id is None:
        return True
    return any(role.id == role_id for role in member.roles)


def get_applications_channel_id() -> int | None:
    raw = os.getenv("APPLICATIONS_CHANNEL_ID", "").strip()
    if raw in _PLACEHOLDERS:
        return None
    try:
        return int(raw)
    except ValueError:
        return None