import discord


async def get_user_safe(bot: discord.Client, user_id: int) -> discord.User | None:
    """Вернуть пользователя, не роняя обработчик при удалённом аккаунте."""
    user = bot.get_user(user_id)
    if user is not None:
        return user
    try:
        return await bot.fetch_user(user_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None
