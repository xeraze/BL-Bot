import logging

import discord
from discord.ext import commands

from utils.applications import (
    ACTIVE_STATUSES,
    get_active_dialogue_by_user,
    get_application,
    get_application_by_thread,
    load_applications,
    update_application,
)
from utils.constants import EMBED_COLOR
from utils.i18n import DEFAULT_LANG, coerce_lang, get_lang, status_label, t
from utils.permissions import member_has_role
from utils.users import get_user_safe

log = logging.getLogger("bl-bot.reviews")


def base_embed(**kwargs) -> discord.Embed:
    return discord.Embed(color=EMBED_COLOR, **kwargs)


def build_application_embed(
    application: dict,
    user: discord.User | discord.Member,
    lang: str = DEFAULT_LANG,
) -> discord.Embed:
    embed = base_embed(
        title=t(lang, "app.embed_title", job=application["job_title"]),
        description=(
            t(lang, "app.candidate", mention=user.mention, id=user.id)
            + "\n"
            + t(lang, "app.status_line", label=status_label(application["status"], lang))
            + "\n"
            + t(lang, "app.name_age_line", value=application["name_age"])
        ),
    )
    embed.add_field(
        name=t(lang, "app.field_experience"),
        value=application["experience"],
        inline=False,
    )

    if application.get("portfolio"):
        embed.add_field(
            name=t(lang, "app.field_portfolio"),
            value=application["portfolio"],
            inline=False,
        )

    if application.get("comment"):
        embed.add_field(
            name=t(lang, "app.field_comment"),
            value=application["comment"],
            inline=False,
        )

    embed.add_field(
        name=t(lang, "app.field_job_desc"),
        value=application["job_description"][:1024],
        inline=False,
    )
    if application.get("job_requirements"):
        embed.add_field(
            name=t(lang, "app.field_job_req"),
            value=application["job_requirements"][:1024],
            inline=False,
        )

    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=t(lang, "app.id_footer", id=application["id"]))
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
    def __init__(self, guild_name: str, lang: str = DEFAULT_LANG) -> None:
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label=t(lang, "common.sent_from", guild=guild_name),
                style=discord.ButtonStyle.secondary,
                disabled=True,
            )
        )


class StatusReasonModal(discord.ui.Modal, title="Reason (optional)"):
    reason = discord.ui.TextInput(
        label="Reason",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000,
        placeholder="State the reason for accepting or rejecting (optional)",
    )

    def __init__(
        self,
        app_id: str,
        new_status: str,
        reviewer: discord.Member,
        guild: discord.Guild | None,
        lang: str = DEFAULT_LANG,
    ) -> None:
        super().__init__(title=t(lang, "common.reason_title"))
        self.lang = lang
        self.reason.label = t(lang, "common.reason_label")
        self.reason.placeholder = t(lang, "common.reason_ph")
        self.app_id = app_id
        self.new_status = new_status
        self.reviewer = reviewer
        self.guild = guild

    async def on_submit(self, interaction: discord.Interaction) -> None:
        lang = self.lang
        application = get_application(self.app_id)
        if application is None:
            await interaction.response.send_message(
                t(lang, "app.not_found"),
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
            lang=lang,
        )
        if application is None:
            await interaction.response.send_message(
                t(lang, "app.update_fail"),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            t(lang, "app.status_updated", label=status_label(self.new_status, lang)),
            ephemeral=True,
        )


class ApplicationReviewSelect(discord.ui.Select):
    def __init__(
        self,
        app_id: str,
        status: str,
        has_thread: bool,
        lang: str = DEFAULT_LANG,
    ) -> None:
        options: list[discord.SelectOption] = []

        if status == "new":
            options = [
                discord.SelectOption(label=t(lang, "common.accept"), value="accept", emoji="✅"),
                discord.SelectOption(label=t(lang, "common.reject"), value="reject", emoji="❌"),
                discord.SelectOption(
                    label=t(lang, "common.reviewing"),
                    value="reviewing",
                    emoji="🔍",
                ),
            ]
        elif status == "reviewing":
            options = [
                discord.SelectOption(label=t(lang, "common.accept"), value="accept", emoji="✅"),
                discord.SelectOption(label=t(lang, "common.reject"), value="reject", emoji="❌"),
            ]
            if not has_thread:
                options.append(
                    discord.SelectOption(
                        label=t(lang, "common.start_dialogue"),
                        value="dialogue",
                        emoji="💬",
                    )
                )

        super().__init__(
            placeholder=t(lang, "app.action_ph"),
            options=options,
            custom_id=f"bl_app_review:{app_id}",
        )
        self.app_id = app_id

    async def callback(self, interaction: discord.Interaction) -> None:
        lang = get_lang(interaction)
        if not isinstance(interaction.user, discord.Member) or not member_has_role(
            interaction.user, "ROLE_JOBS_MANAGE"
        ):
            await interaction.response.send_message(
                t(lang, "app.no_permission"),
                ephemeral=True,
            )
            return

        application = get_application(self.app_id)
        if application is None:
            await interaction.response.send_message(
                t(lang, "app.not_found"),
                ephemeral=True,
            )
            return

        action = self.values[0]
        reviewer = interaction.user

        if action in ("accept", "reject"):
            new_status = {"accept": "accepted", "reject": "rejected"}[action]
            await interaction.response.send_modal(
                StatusReasonModal(self.app_id, new_status, reviewer, interaction.guild, lang)
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
                lang=lang,
            )
            if application is None:
                await interaction.response.send_message(
                    t(lang, "app.update_fail"),
                    ephemeral=True,
                )
                return

            await interaction.response.send_message(
                t(lang, "app.status_updated", label=status_label(new_status, lang)),
                ephemeral=True,
            )
            return

        if action == "dialogue":
            await interaction.response.defer(ephemeral=True)
            await start_dialogue(
                interaction.client, application, reviewer, interaction.guild, lang=lang
            )
            await interaction.followup.send(
                t(lang, "app.dialogue_started"), ephemeral=True
            )


class ApplicationReviewView(discord.ui.View):
    def __init__(
        self,
        app_id: str,
        status: str,
        has_thread: bool = False,
        lang: str = DEFAULT_LANG,
    ) -> None:
        super().__init__(timeout=None)
        if status in ACTIVE_STATUSES:
            self.add_item(ApplicationReviewSelect(app_id, status, has_thread, lang))


async def apply_status_change(
    bot: discord.Client,
    application: dict,
    new_status: str,
    reviewer: discord.Member,
    guild: discord.Guild | None,
    reason: str | None = None,
    lang: str = DEFAULT_LANG,
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
    await refresh_application_message(bot, application, lang)
    return application


async def notify_status_change(
    bot: discord.Client,
    application: dict,
    new_status: str,
    reviewer: discord.Member,
    guild: discord.Guild | None,
) -> None:
    user = await get_user_safe(bot, application["user_id"])
    if user is None:
        log.warning("Пользователь %s не найден, уведомление о статусе не отправлено", application["user_id"])
        return
    lang = coerce_lang(application.get("lang"))
    label = status_label(new_status, lang)

    embed = base_embed(
        title=t(lang, "app.dm_status_title"),
        description=t(lang, "app.dm_status_desc", job=application["job_title"], label=label),
    )

    if application.get("review_reason"):
        embed.add_field(
            name=t(lang, "common.reason_label"),
            value=application["review_reason"][:1024],
            inline=False,
        )

    embed.set_footer(text=t(lang, "app.changed_by", name=reviewer.display_name))
    view = ServerInfoView(guild.name, lang) if guild else None

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
    user = await get_user_safe(bot, application["user_id"])
    if user is None:
        log.warning("Пользователь %s не найден, уведомление о диалоге не отправлено", application["user_id"])
        return
    lang = coerce_lang(application.get("lang"))

    embed = base_embed(
        title=t(lang, "app.dm_dialogue_title", job=application["job_title"]),
        description=t(lang, "app.dm_dialogue_desc", reviewer=reviewer.mention),
    )
    view = ServerInfoView(guild.name, lang) if guild else None

    try:
        await user.send(embed=embed, view=view)
    except discord.Forbidden:
        log.warning("Не удалось отправить ЛС о диалоге пользователю %s", application["user_id"])


async def refresh_application_message(
    bot: discord.Client,
    application: dict,
    lang: str = DEFAULT_LANG,
) -> None:
    if not application.get("message_id") or not application.get("channel_id"):
        return

    channel = bot.get_channel(application["channel_id"])
    if channel is None:
        return

    try:
        message = await channel.fetch_message(application["message_id"])
    except discord.NotFound:
        return

    user = await get_user_safe(bot, application["user_id"])
    if user is None:
        log.warning("Пользователь %s не найден, сообщение заявки не обновлено", application["user_id"])
        return
    embed = build_application_embed(application, user, lang)

    has_thread = bool(application.get("thread_id"))
    status = application["status"]
    view = None
    if status in ACTIVE_STATUSES:
        view = ApplicationReviewView(application["id"], status, has_thread, lang)

    await message.edit(embed=embed, view=view)


async def start_dialogue(
    bot: discord.Client,
    application: dict,
    reviewer: discord.Member,
    guild: discord.Guild | None,
    lang: str = DEFAULT_LANG,
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

    thread_name = t(lang, "app.thread_name", job=application["job_title"])[:100]
    thread = await message.create_thread(name=thread_name, auto_archive_duration=10080)

    application = update_application(
        application["id"],
        thread_id=thread.id,
        reviewer_id=reviewer.id,
    )
    if application is None:
        return

    await notify_dialogue_started(bot, application, reviewer, guild)
    await refresh_application_message(bot, application, lang)

    welcome = base_embed(
        title=t(lang, "app.welcome_title"),
        description=t(
            lang,
            "app.welcome_desc",
            reviewer=reviewer.mention,
            candidate=f"<@{application['user_id']}>",
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

            user = await get_user_safe(self.bot, application["user_id"])
            if user is None:
                return
            embed = message_relay_embed(message.author, message.content, show_footer=False)
            try:
                await user.send(embed=embed)
            except discord.Forbidden:
                await message.channel.send(
                    t(DEFAULT_LANG, "app.relay_dm_closed"),
                    delete_after=10,
                )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Reviews(bot))
