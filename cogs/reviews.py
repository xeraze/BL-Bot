import logging

import discord
from discord.ext import commands

from utils.applications import (
    STATUS_LABELS,
    ACTIVE_STATUSES,
    get_active_dialogue_by_user,
    get_application,
    get_application_by_thread,
    load_applications,
    update_application,
)
from utils.constants import EMBED_COLOR
from utils.permissions import member_has_role

log = logging.getLogger("bl-bot.reviews")


def base_embed(**kwargs) -> discord.Embed:
    return discord.Embed(color=EMBED_COLOR, **kwargs)


def build_application_embed(application: dict, user: discord.User | discord.Member) -> discord.Embed:
    status_label = STATUS_LABELS.get(application["status"], application["status"])
    embed = base_embed(
        title=f"📩 Заявка: {application['job_title']}",
        description=(
            f"**Кандидат:** {user.mention} (`{user.id}`)\n"
            f"**Статус:** `{status_label}`\n"
            f"**Имя и возраст:** {application['name_age']}"
        ),
    )
    embed.add_field(name="Опыт", value=application["experience"], inline=False)

    if application.get("portfolio"):
        embed.add_field(name="Портфолио / контакты", value=application["portfolio"], inline=False)

    if application.get("comment"):
        embed.add_field(name="Комментарий", value=application["comment"], inline=False)

    embed.add_field(
        name="Описание должности",
        value=application["job_description"][:1024],
        inline=False,
    )
    if application.get("job_requirements"):
        embed.add_field(
            name="Требования к должности",
            value=application["job_requirements"][:1024],
            inline=False,
        )

    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"ID заявки: {application['id']}")
    return embed


def message_relay_embed(
    author: discord.User | discord.Member,
    content: str,
    show_footer: bool = False,
) -> discord.Embed:
    embed = base_embed(description=content)
    embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)
    if show_footer:
        embed.set_footer(text=f"{author.name}#{author.discriminator} | {author.id}")
    return embed


class ServerInfoView(discord.ui.View):
    def __init__(self, guild_name: str) -> None:
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label=f"Отправлено с {guild_name}",
                style=discord.ButtonStyle.secondary,
                disabled=True,
            )
        )


class StatusReasonModal(discord.ui.Modal, title="Причина (необязательно)"):
    reason = discord.ui.TextInput(
        label="Причина",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000,
        placeholder="Укажите причину принятия или отклонения (необязательно)",
    )

    def __init__(
        self,
        app_id: str,
        new_status: str,
        reviewer: discord.Member,
        guild: discord.Guild | None,
    ) -> None:
        super().__init__()
        self.app_id = app_id
        self.new_status = new_status
        self.reviewer = reviewer
        self.guild = guild

    async def on_submit(self, interaction: discord.Interaction) -> None:
        application = get_application(self.app_id)
        if application is None:
            await interaction.response.send_message(
                "Заявка не найдена.",
                ephemeral=True,
            )
            return

        reason = self.reason.value.strip() or None
        application = await apply_status_change(
            interaction.client,
            application,
            self.new_status,
            self.reviewer,
            self.guild,
            reason=reason,
        )
        if application is None:
            await interaction.response.send_message(
                "Не удалось обновить заявку.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"Статус заявки обновлён: `{STATUS_LABELS[self.new_status]}`.",
            ephemeral=True,
        )


class ApplicationReviewSelect(discord.ui.Select):
    def __init__(self, app_id: str, status: str, has_thread: bool) -> None:
        options: list[discord.SelectOption] = []

        if status == "new":
            options = [
                discord.SelectOption(label="Принять", value="accept", emoji="✅"),
                discord.SelectOption(label="Отклонить", value="reject", emoji="❌"),
                discord.SelectOption(
                    label="На рассмотрении",
                    value="reviewing",
                    emoji="🔍",
                ),
            ]
        elif status == "reviewing":
            options = [
                discord.SelectOption(label="Принять", value="accept", emoji="✅"),
                discord.SelectOption(label="Отклонить", value="reject", emoji="❌"),
            ]
            if not has_thread:
                options.append(
                    discord.SelectOption(
                        label="Начать диалог",
                        value="dialogue",
                        emoji="💬",
                    )
                )

        super().__init__(
            placeholder="Действие с заявкой",
            options=options,
            custom_id=f"bl_app_review:{app_id}",
        )
        self.app_id = app_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.user, discord.Member) or not member_has_role(
            interaction.user, "ROLE_JOBS_MANAGE"
        ):
            await interaction.response.send_message(
                "У вас нет прав для проверки заявок.",
                ephemeral=True,
            )
            return

        application = get_application(self.app_id)
        if application is None:
            await interaction.response.send_message(
                "Заявка не найдена.",
                ephemeral=True,
            )
            return

        action = self.values[0]
        reviewer = interaction.user

        if action in ("accept", "reject"):
            new_status = {"accept": "accepted", "reject": "rejected"}[action]
            await interaction.response.send_modal(
                StatusReasonModal(self.app_id, new_status, reviewer, interaction.guild)
            )
            return

        if action == "reviewing":
            new_status = "reviewing"
            application = await apply_status_change(
                interaction.client,
                application,
                new_status,
                reviewer,
                interaction.guild,
            )
            if application is None:
                await interaction.response.send_message(
                    "Не удалось обновить заявку.",
                    ephemeral=True,
                )
                return

            await interaction.response.send_message(
                f"Статус заявки обновлён: `{STATUS_LABELS[new_status]}`.",
                ephemeral=True,
            )
            return

        if action == "dialogue":
            await interaction.response.defer(ephemeral=True)
            await start_dialogue(interaction.client, application, reviewer, interaction.guild)
            await interaction.followup.send("Диалог с кандидатом начат.", ephemeral=True)


class ApplicationReviewView(discord.ui.View):
    def __init__(self, app_id: str, status: str, has_thread: bool = False) -> None:
        super().__init__(timeout=None)
        if status in ACTIVE_STATUSES:
            self.add_item(ApplicationReviewSelect(app_id, status, has_thread))


async def apply_status_change(
    bot: discord.Client,
    application: dict,
    new_status: str,
    reviewer: discord.Member,
    guild: discord.Guild | None,
    reason: str | None = None,
) -> dict | None:
    application = update_application(
        application["id"],
        status=new_status,
        reviewer_id=reviewer.id,
        review_reason=reason,
    )
    if application is None:
        return None

    await notify_status_change(bot, application, new_status, reviewer, guild)
    await refresh_application_message(bot, application)
    return application


async def notify_status_change(
    bot: discord.Client,
    application: dict,
    new_status: str,
    reviewer: discord.Member,
    guild: discord.Guild | None,
) -> None:
    user = bot.get_user(application["user_id"]) or await bot.fetch_user(application["user_id"])
    status_label = STATUS_LABELS.get(new_status, new_status)

    description = (
        f"Статус вашей заявки **{application['job_title']}** "
        f"изменён на `{status_label}`"
    )
    embed = base_embed(
        title="Статус вашей заявки изменён",
        description=description,
    )

    if application.get("review_reason"):
        embed.add_field(
            name="Причина",
            value=application["review_reason"][:1024],
            inline=False,
        )

    embed.set_footer(text=f"Изменил: {reviewer.display_name}")
    view = ServerInfoView(guild.name) if guild else None

    try:
        await user.send(embed=embed, view=view)
    except discord.Forbidden:
        log.warning("Не удалось отправить ЛС пользователю %s", application["user_id"])


async def notify_dialogue_started(
    bot: discord.Client,
    application: dict,
    reviewer: discord.Member,
    guild: discord.Guild | None,
) -> None:
    user = bot.get_user(application["user_id"]) or await bot.fetch_user(application["user_id"])

    embed = base_embed(
        title=f"Начат диалог — {application['job_title']}",
        description=(
            f"Проверяющий {reviewer.mention} начал с вами **диалог**.\n\n"
            "Все сообщения, которые вы пишете боту в ЛС — видит проверяющий."
        ),
    )
    view = ServerInfoView(guild.name) if guild else None

    try:
        await user.send(embed=embed, view=view)
    except discord.Forbidden:
        log.warning("Не удалось отправить ЛС о диалоге пользователю %s", application["user_id"])


async def refresh_application_message(bot: discord.Client, application: dict) -> None:
    if not application.get("message_id") or not application.get("channel_id"):
        return

    channel = bot.get_channel(application["channel_id"])
    if channel is None:
        return

    try:
        message = await channel.fetch_message(application["message_id"])
    except discord.NotFound:
        return

    user = bot.get_user(application["user_id"]) or await bot.fetch_user(application["user_id"])
    embed = build_application_embed(application, user)

    has_thread = bool(application.get("thread_id"))
    status = application["status"]
    view = None
    if status in ACTIVE_STATUSES:
        view = ApplicationReviewView(application["id"], status, has_thread)

    await message.edit(embed=embed, view=view)


async def start_dialogue(
    bot: discord.Client,
    application: dict,
    reviewer: discord.Member,
    guild: discord.Guild | None,
) -> None:
    if application.get("thread_id"):
        return

    channel = bot.get_channel(application["channel_id"])
    if channel is None:
        return

    try:
        message = await channel.fetch_message(application["message_id"])
    except discord.NotFound:
        return

    thread_name = f"Диалог — {application['job_title']}"[:100]
    thread = await message.create_thread(name=thread_name, auto_archive_duration=10080)

    application = update_application(
        application["id"],
        thread_id=thread.id,
        reviewer_id=reviewer.id,
    )
    if application is None:
        return

    await notify_dialogue_started(bot, application, reviewer, guild)
    await refresh_application_message(bot, application)

    welcome = base_embed(
        title="Диалог с кандидатом",
        description=(
            f"Проверяющий: {reviewer.mention}\n"
            f"Кандидат: <@{application['user_id']}>\n\n"
            "Пишите в эту ветку — сообщения придут кандидату в ЛС.\n"
            "Ответы кандидата в ЛС боту тоже появятся здесь."
        ),
    )
    await thread.send(embed=welcome)


class Reviews(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        for application in load_applications():
            if application["status"] in ACTIVE_STATUSES:
                self.bot.add_view(
                    ApplicationReviewView(
                        application["id"],
                        application["status"],
                        bool(application.get("thread_id")),
                    )
                )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.content:
            return

        if message.guild is None:
            application = get_active_dialogue_by_user(message.author.id)
            if application is None:
                return

            thread = self.bot.get_channel(application["thread_id"])
            if not isinstance(thread, discord.Thread):
                return

            embed = message_relay_embed(message.author, message.content, show_footer=True)
            await thread.send(embed=embed)
            return

        if isinstance(message.channel, discord.Thread):
            application = get_application_by_thread(message.channel.id)
            if application is None:
                return

            user = self.bot.get_user(application["user_id"]) or await self.bot.fetch_user(
                application["user_id"]
            )
            embed = message_relay_embed(message.author, message.content, show_footer=False)
            try:
                await user.send(embed=embed)
            except discord.Forbidden:
                await message.channel.send(
                    "⚠️ Не удалось доставить сообщение — у кандидата закрыты ЛС.",
                    delete_after=10,
                )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Reviews(bot))
