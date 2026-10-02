import os
import re
import discord
from discord import app_commands
from discord.ext import commands

from cogs.reviews import ApplicationReviewView, build_application_embed, message_relay_embed
from utils.applications import create_application, update_application
from utils.constants import EMBED_COLOR
from utils.ideas import (
    IDEA_ACTIVE_STATUSES,
    create_idea,
    load_ideas,
    save_idea,
)
from utils.permissions import (
    get_applications_channel_id,
    has_role,
    member_has_role,
)
from utils.storage import add_job, load_jobs, remove_job
from utils.users import get_user_safe


def base_embed(**kwargs) -> discord.Embed:
    return discord.Embed(color=EMBED_COLOR, **kwargs)


def _job_requirements(job: dict) -> str:
    return job.get("requirements") or job.get("footer", "")


def _parse_channel_id(env_key: str) -> int | None:
    raw = os.getenv(env_key, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def get_idea_review_channel_id() -> int | None:
    return _parse_channel_id("IDEA_REVIEW_CHANNEL_ID")


def get_ideas_channel_id() -> int | None:
    return _parse_channel_id("IDEA_PUBLIC_CHANNEL_ID")


IDEA_DIALOGUE_BY_USER: dict[int, int] = {}
IDEA_USER_BY_THREAD: dict[int, int] = {}

MAX_EMBED_FIELD = 1024
EMBED_TOTAL_BUDGET = 5900
JOB_SEPARATOR = "\n\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"


def format_job_block(index: int, job: dict) -> str:
    requirements = _job_requirements(job)
    block = f"**{index}. {job['title']}**\n{job['description']}"
    if requirements:
        block += f"\n\n**Требования:**\n{requirements}"
    return block


def _split_text(text: str, limit: int = MAX_EMBED_FIELD) -> list[str]:
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def build_jobs_embed() -> discord.Embed:
    jobs = load_jobs()

    embed = base_embed(
        title="📋 Вакансии студии",
        description=(
            "Ниже — открытые позиции в студии.\n"
            "Выберите должность в меню под сообщением, чтобы подать заявку."
        ),
    )

    if not jobs:
        embed.description = "На данный момент открытых вакансий нет. Загляните позже!"
        return embed

    head_chars = len(embed.title) + len(embed.description)
    fields: list[str] = []
    current = ""
    shown = 0
    stopped = False

    for index, job in enumerate(jobs, start=1):
        for part in _split_text(format_job_block(index, job)):
            piece = part if not current else JOB_SEPARATOR + part
            if len(current) + len(piece) > MAX_EMBED_FIELD:
                fields.append(current)
                current = ""
                piece = part
            if head_chars + sum(map(len, fields)) + len(piece) > EMBED_TOTAL_BUDGET:
                stopped = True
                break
            current = piece
        if stopped:
            break
        shown += 1

    if current:
        fields.append(current)

    for position, value in enumerate(fields):
        name = "Открытые вакансии" if position == 0 else "Открытые вакансии (продолжение)"
        embed.add_field(name=name, value=value, inline=False)

    footer = f"Всего позиций: {len(jobs)}"
    if shown < len(jobs):
        footer += f" · показано {shown}, уберите лишние через /bl уработа"
    embed.set_footer(text=footer)
    return embed


class NewsModal(discord.ui.Modal, title="Публикация новости"):
    title_input = discord.ui.TextInput(
        label="Название новости",
        placeholder="Заголовок новости...",
        max_length=256,
        required=True,
    )
    description_input = discord.ui.TextInput(
        label="Описание новости",
        placeholder="Текст новости...",
        style=discord.TextStyle.paragraph,
        max_length=4000,
        required=True,
    )
    image_input = discord.ui.TextInput(
        label="Изображение (необязательно)",
        placeholder="https://example.com/image.png",
        required=False,
        max_length=500,
    )
    pings_input = discord.ui.TextInput(
        label="Пинги ролей (необязательно)",
        placeholder="<@&1234>, <@&5678>",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=200,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        embed = base_embed(
            title=self.title_input.value,
            description=self.description_input.value,
        )

        image_url = self.image_input.value.strip()
        if image_url:
            if not image_url.startswith(("http://", "https://")):
                await interaction.response.send_message(
                    "Ссылка на изображение должна начинаться с `http://` или `https://`.",
                    ephemeral=True,
                )
                return
            embed.set_image(url=image_url)

        if interaction.channel is None:
            await interaction.response.send_message(
                "Не удалось определить канал для публикации.",
                ephemeral=True,
            )
            return

        pings = self.pings_input.value.strip()
        mentions = []
        if pings:
            items = [item.strip() for item in pings.split(",") if item.strip()]
            for item in items:
                match = re.fullmatch(r"<@&([0-9]+)>", item)
                if not match:
                    await interaction.response.send_message(
                        "Пинги должны быть в формате `<@&1234>` через запятую, до 5 ролей.",
                        ephemeral=True,
                    )
                    return
                mentions.append(match.group(1))

            mentions = list(dict.fromkeys(mentions))
            if len(mentions) > 5:
                await interaction.response.send_message(
                    "Можно указать не более 5 пинг ролей.",
                    ephemeral=True,
                )
                return

        await interaction.response.defer(ephemeral=True)

        try:
            if mentions:
                mention_text = " ".join(f"<@&{role_id}>" for role_id in mentions)
                await interaction.channel.send(content=mention_text, embed=embed)
            else:
                await interaction.channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            await interaction.followup.send(
                "❌ Не удалось опубликовать новость в этом канале. Проверьте права бота.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            "✅ Новость опубликована в канал.",
            ephemeral=True,
        )


class NewsEditButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(
            label="Изменить текст",
            style=discord.ButtonStyle.primary,
            emoji="🎨",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(NewsModal())


class NewsPreviewView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=300)
        self.add_item(NewsEditButton())


class IdeaStatusReasonModal(discord.ui.Modal, title="Причина (необязательно)"):
    reason = discord.ui.TextInput(
        label="Причина",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000,
        placeholder="Укажите причину принятия или отклонения (необязательно)",
    )

    def __init__(self, idea_view: "IdeaApprovalView", action: str) -> None:
        super().__init__()
        self.idea_view = idea_view
        self.action = action

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if self.idea_view is None:
            await interaction.response.send_message(
                "Не удалось обработать решение.",
                ephemeral=True,
            )
            return
        await self.idea_view.process_decision(
            interaction,
            self.action,
            self.reason.value.strip() or None,
            reason_collected=True,
        )


class IdeaReviewButton(discord.ui.Button):
    def __init__(self, idea_id: str, label: str, style: discord.ButtonStyle, action: str) -> None:
        super().__init__(
            label=label,
            style=style,
            custom_id=f"bl_idea:{idea_id}:{action}",
        )
        self.action = action

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if view is None or not isinstance(view, IdeaApprovalView):
            await interaction.response.send_message(
                "Не удалось обработать решение.",
                ephemeral=True,
            )
            return

        await view.process_decision(interaction, self.action)


class IdeaApprovalView(discord.ui.View):
    STATUS_LABELS = {
        "new": "Новая идея",
        "reviewing": "На рассмотрении",
        "accepted": "Принята",
        "rejected": "Отклонена",
        "dialogue": "Диалог начат",
    }

    def __init__(self, bot: discord.Client, record: dict) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.record = record
        self._rebuild_buttons()

    @property
    def idea_id(self) -> str:
        return self.record["id"]

    @property
    def idea_text(self) -> str:
        return self.record["text"]

    def _rebuild_buttons(self) -> None:
        self.clear_items()
        status = self.record["status"]
        if status == "new":
            self.add_item(IdeaReviewButton(self.idea_id, "Принять", discord.ButtonStyle.success, "accept"))
            self.add_item(IdeaReviewButton(self.idea_id, "Отклонить", discord.ButtonStyle.danger, "reject"))
            self.add_item(IdeaReviewButton(self.idea_id, "На рассмотрении", discord.ButtonStyle.secondary, "reviewing"))
        else:
            self.add_item(IdeaReviewButton(self.idea_id, "Принять", discord.ButtonStyle.success, "accept"))
            self.add_item(IdeaReviewButton(self.idea_id, "Отклонить", discord.ButtonStyle.danger, "reject"))
            dialogue = IdeaReviewButton(self.idea_id, "Начать диалог", discord.ButtonStyle.secondary, "dialogue")
            dialogue.disabled = status != "reviewing"
            self.add_item(dialogue)
        if self.record.get("decision_made"):
            self.disable_all_items()

    def _save(self) -> None:
        save_idea(self.record)

    def disable_all_items(self) -> None:
        for item in self.children:
            item.disabled = True

    def build_embed(self) -> discord.Embed:
        embed = base_embed(
            title="Новая идея",
            description=self.idea_text[:4096],
        )
        embed.add_field(name="От:", value=f"<@{self.record['author_id']}>", inline=False)
        embed.add_field(
            name="Статус:",
            value=self.STATUS_LABELS.get(self.record["status"], self.record["status"]),
            inline=False,
        )
        if self.record.get("reviewer_id"):
            embed.add_field(
                name="Выполнил:",
                value=f"<@{self.record['reviewer_id']}>",
                inline=False,
            )
        if self.record.get("review_reason"):
            embed.add_field(
                name="Причина:",
                value=self.record["review_reason"][:1024],
                inline=False,
            )
        return embed

    async def process_decision(
        self,
        interaction: discord.Interaction,
        action: str,
        reason: str | None = None,
        *,
        reason_collected: bool = False,
    ) -> None:
        if not isinstance(interaction.user, discord.Member) or not member_has_role(
            interaction.user, "IDEA_APPROVER_ROLE_ID"
        ):
            await interaction.response.send_message(
                "У вас нет прав для проверки идей.",
                ephemeral=True,
            )
            return

        if self.record.get("decision_made"):
            await interaction.response.send_message(
                "По этой идее уже принято решение.",
                ephemeral=True,
            )
            return

        if action in ("accept", "reject") and reason is None and not reason_collected:
            await interaction.response.send_modal(IdeaStatusReasonModal(self, action))
            return

        if action == "accept":
            self.record.update(
                status="accepted",
                reviewer_id=interaction.user.id,
                reviewer_name=interaction.user.display_name,
                review_reason=reason,
                decision_made=True,
            )
            self._save()
            self._rebuild_buttons()
            await self._finalize_decision(interaction, accepted=True)
            return

        if action == "reject":
            self.record.update(
                status="rejected",
                reviewer_id=interaction.user.id,
                reviewer_name=interaction.user.display_name,
                review_reason=reason,
                decision_made=True,
            )
            self._save()
            self._rebuild_buttons()
            await self._finalize_decision(interaction, accepted=False)
            return

        if action == "reviewing":
            self.record.update(
                status="reviewing",
                reviewer_id=interaction.user.id,
                reviewer_name=interaction.user.display_name,
            )
            self._save()
            self._rebuild_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
            await self._notify_author(
                interaction.client,
                "Ваша идея отправлена на рассмотрение",
                "Проверяющий начал рассматривать вашу идею. Статус будет обновлён позже.",
                interaction.guild,
            )
            return

        if action == "dialogue":
            if self.record["status"] != "reviewing":
                await interaction.response.send_message(
                    "Сначала поставьте идею на рассмотрение.",
                    ephemeral=True,
                )
                return
            thread = await self._create_dialogue_thread(interaction)
            if thread is None:
                await interaction.response.send_message(
                    "Не удалось создать ветку диалога.",
                    ephemeral=True,
                )
                return
            self.record.update(
                status="dialogue",
                reviewer_id=interaction.user.id,
                reviewer_name=interaction.user.display_name,
            )
            self._save()
            self._rebuild_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
            await self._notify_author(
                interaction.client,
                "Начат диалог по вашей идее",
                "Проверяющий начал диалог по вашей идее. Все дальнейшее взаимодействие с проверяющим будет происходить в этой ветке. Ваши сообщения логгируются!",
                interaction.guild,
            )
            return

    async def _create_dialogue_thread(self, interaction: discord.Interaction) -> discord.Thread | None:
        if interaction.message is None:
            return None

        try:
            thread_name = f"Диалог — идея от {self.record['author_name']}"[:100]
            thread = await interaction.message.create_thread(
                name=thread_name,
                auto_archive_duration=10080,
            )
        except Exception:
            return None

        self.record["thread_id"] = thread.id
        self._save()
        IDEA_DIALOGUE_BY_USER[self.record["author_id"]] = thread.id
        IDEA_USER_BY_THREAD[thread.id] = self.record["author_id"]

        welcome = base_embed(
            title="Начат диалог",
            description=(
                f"Вы начали диалог с {interaction.user.mention} по его идее.\n\n"
                "Сообщения автора из ЛС будут приходить сюда, ваши сообщения будут отправляться пользователю в ЛС."
            ),
        )
        await thread.send(embed=welcome)
        return thread

    async def _publish_accepted_idea(self, interaction: discord.Interaction) -> None:
        idea_channel_id = get_ideas_channel_id()
        if idea_channel_id is None:
            return

        idea_channel = interaction.client.get_channel(idea_channel_id)
        if idea_channel is None:
            try:
                idea_channel = await interaction.client.fetch_channel(idea_channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return

        public_embed = base_embed(
            title="Новая идея",
            description=self.idea_text[:4096],
        )
        public_embed.set_author(
            name=f"От: {self.record['author_name']}",
            icon_url=self.record["author_avatar"],
        )
        message = await idea_channel.send(
            content=f"<@{self.record['author_id']}>",
            embed=public_embed,
        )
        await message.add_reaction("👍")
        await message.add_reaction("👎")

    async def _finalize_decision(
        self,
        interaction: discord.Interaction,
        accepted: bool,
    ) -> None:
        status_text = "принята" if accepted else "отклонена"
        await interaction.response.edit_message(
            content=f"✅ Идея {status_text} {interaction.user.mention}.",
            embed=self.build_embed(),
            view=self,
        )
        title = "Ваша идея принята" if accepted else "Ваша идея отклонена"
        description = (
            "Ваша идея принята. Спасибо за ваш вклад!" if accepted else "Ваша идея отклонена. Присылайте другие идеи, мы всегда рады новым предложениям!"
        )
        if accepted:
            await self._publish_accepted_idea(interaction)
        await self._notify_author(
            interaction.client,
            title,
            description,
            interaction.guild,
        )

    async def _notify_author(
        self,
        bot: discord.Client,
        title: str,
        description: str,
        guild: discord.Guild | None,
    ) -> None:
        embed = base_embed(title=title, description=description)
        if self.record.get("review_reason"):
            embed.add_field(
                name="Причина:",
                value=self.record["review_reason"][:1024],
                inline=False,
            )
        if self.record.get("reviewer_name"):
            embed.set_footer(text=f"Проверил: {self.record['reviewer_name']}")
        view = None
        if guild is not None:
            view = discord.ui.View(timeout=None)
            view.add_item(
                discord.ui.Button(
                    label=f"Отправлено с {guild.name}",
                    style=discord.ButtonStyle.secondary,
                    disabled=True,
                )
            )
        author = await get_user_safe(bot, self.record["author_id"])
        if author is None:
            return
        try:
            await author.send(embed=embed, view=view)
        except discord.Forbidden:
            pass


class AddJobModal(discord.ui.Modal, title="Добавление вакансии"):
    title_input = discord.ui.TextInput(
        label="Название должности",
        placeholder="Например: Разработчик, Дизайнер и т.д",
        max_length=100,
        required=True,
    )
    description_input = discord.ui.TextInput(
        label="Описание должности",
        placeholder="Обязанности, условия, что предстоит делать...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )
    requirements_input = discord.ui.TextInput(
        label="Требования",
        placeholder="Опыт, навыки, что нужно от кандидата...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        job = add_job(
            title=self.title_input.value,
            description=self.description_input.value,
            requirements=self.requirements_input.value,
        )
        await interaction.response.send_message(
            f"✅ Вакансия **{job['title']}** добавлена в список.",
            ephemeral=True,
        )


class JobApplicationModal(discord.ui.Modal):
    def __init__(self, job: dict) -> None:
        super().__init__(title=f"Заявка: {job['title'][:37]}")
        self.job = job

        self.name_age = discord.ui.TextInput(
            label="Имя и возраст",
            placeholder="Например: Алексей, 18 лет",
            max_length=100,
            required=True,
        )
        self.experience = discord.ui.TextInput(
            label="Опыт",
            placeholder="Расскажите о своём опыте в данной сфере...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True,
        )
        self.portfolio = discord.ui.TextInput(
            label="Портфолио / контакты",
            placeholder="Ссылки на работы, Discord, Telegram...",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False,
        )
        self.comment = discord.ui.TextInput(
            label="Комментарий (необязательно)",
            placeholder="Почему хотите к нам, дополнительная информация...",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False,
        )

        self.add_item(self.name_age)
        self.add_item(self.experience)
        self.add_item(self.portfolio)
        self.add_item(self.comment)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        channel_id = get_applications_channel_id()
        if channel_id is None:
            await interaction.response.send_message(
                "Канал для заявок не настроен. Сообщите STAFF.",
                ephemeral=True,
            )
            return

        channel = interaction.client.get_channel(channel_id)
        if channel is None:
            await interaction.response.send_message(
                "Канал для заявок не найден. Сообщите STAFF.",
                ephemeral=True,
            )
            return

        job = self.job
        portfolio = self.portfolio.value.strip()
        comment = self.comment.value.strip()

        application = create_application(
            user_id=interaction.user.id,
            job={
                **job,
                "requirements": _job_requirements(job),
            },
            name_age=self.name_age.value,
            experience=self.experience.value,
            portfolio=portfolio,
            comment=comment,
        )

        embed = build_application_embed(application, interaction.user)
        review_view = ApplicationReviewView(application["id"], "new")
        interaction.client.add_view(review_view)
        message = await channel.send(embed=embed, view=review_view)

        update_application(
            application["id"],
            message_id=message.id,
            channel_id=channel.id,
        )

        await interaction.response.send_message(
            f"✅ Заявка на должность **{job['title']}** отправлена. Ожидайте ответа.",
            ephemeral=True,
        )


class ApplyJobSelect(discord.ui.Select):
    def __init__(self, jobs: list[dict]) -> None:
        options = [
            discord.SelectOption(
                label=job["title"][:100],
                description=job["description"][:100] or None,
                value=job["id"],
            )
            for job in jobs[:25]
        ]
        super().__init__(
            placeholder="Выберите должность для подачи заявки",
            options=options,
            min_values=1,
            max_values=1,
        )
        self.jobs = {job["id"]: job for job in jobs}

    async def callback(self, interaction: discord.Interaction) -> None:
        job = self.jobs[self.values[0]]
        await interaction.response.send_modal(JobApplicationModal(job))


class ApplyJobView(discord.ui.View):
    def __init__(self, jobs: list[dict]) -> None:
        super().__init__(timeout=300)
        self.add_item(ApplyJobSelect(jobs))


class DeleteJobSelect(discord.ui.Select):
    def __init__(self, jobs: list[dict]) -> None:
        options = [
            discord.SelectOption(
                label=job["title"][:100],
                description=(
                    _job_requirements(job)[:100] or job["description"][:100] or None
                ),
                value=job["id"],
            )
            for job in jobs[:25]
        ]
        super().__init__(
            placeholder="Выберите вакансию для удаления",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        job_id = self.values[0]
        removed = remove_job(job_id)

        if removed is None:
            await interaction.response.send_message(
                "Вакансия уже была удалена или не найдена. Обновите список и попробуйте снова.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"🗑️ Вакансия **{removed['title']}** удалена из списка.",
            ephemeral=True,
        )


class DeleteJobView(discord.ui.View):
    def __init__(self, jobs: list[dict]) -> None:
        super().__init__(timeout=300)
        self.add_item(DeleteJobSelect(jobs))


class BLGroup(app_commands.Group):
    """Команды BL Bot."""

    def __init__(self) -> None:
        super().__init__(name="bl", description="Команды студии BL")

    @app_commands.command(
        name="новости",
        description="Опубликовать новость в канал",
    )
    @has_role("ROLE_NEWS")
    async def news(self, interaction: discord.Interaction) -> None:
        preview = base_embed(
            title="Публикация новости",
            description=(
                "Нажмите кнопку ниже, чтобы заполнить поля новости.\n"
                "После отправки формы бот опубликует эмбед в этот канал.\n\n"
                "*Заполните все поля перед отправкой — предпросмотр не обновляется автоматически.*"
            ),
        )
        await interaction.response.send_message(
            embed=preview,
            view=NewsPreviewView(),
            ephemeral=True,
        )

    @app_commands.command(
        name="идея",
        description="Отправить идею на рассмотрение",
    )
    @app_commands.describe(idea="Текст идеи")
    async def idea(self, interaction: discord.Interaction, idea: str) -> None:
        review_channel_id = get_idea_review_channel_id()
        if review_channel_id is None:
            await interaction.response.send_message(
                "Канал для проверки идей не настроен. Сообщите STAFF.",
                ephemeral=True,
            )
            return

        review_channel = interaction.client.get_channel(review_channel_id)
        if review_channel is None:
            try:
                review_channel = await interaction.client.fetch_channel(review_channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                review_channel = None

        if review_channel is None:
            await interaction.response.send_message(
                "Канал для проверки идей не найден. Сообщите STAFF.",
                ephemeral=True,
            )
            return

        idea_text = idea.strip()
        if not idea_text:
            await interaction.response.send_message(
                "Текст идеи не может быть пустым.",
                ephemeral=True,
            )
            return

        record = create_idea(
            author_id=interaction.user.id,
            author_name=interaction.user.display_name,
            author_avatar=interaction.user.display_avatar.url,
            text=idea_text,
        )
        view = IdeaApprovalView(interaction.client, record)
        message = await review_channel.send(embed=view.build_embed(), view=view)
        record.update(channel_id=review_channel.id, message_id=message.id)
        save_idea(record)

        await interaction.response.send_message(
            "✅ Ваша идея отправлена на рассмотрение. Ожидайте ответа.",
            ephemeral=True,
        )

    @app_commands.command(
        name="дработа",
        description="Добавить вакансию в список (без публикации)",
    )
    @has_role("ROLE_JOBS_MANAGE")
    async def add_job(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(AddJobModal())

    @app_commands.command(
        name="уработа",
        description="Удалить вакансию из списка",
    )
    @has_role("ROLE_JOBS_MANAGE")
    async def remove_job_cmd(self, interaction: discord.Interaction) -> None:
        jobs = load_jobs()

        if not jobs:
            await interaction.response.send_message(
                "Список вакансий пуст — удалять нечего.",
                ephemeral=True,
            )
            return

        embed = base_embed(
            title="Удаление вакансии",
            description="Выберите должность из списка ниже, которую нужно убрать.",
        )
        await interaction.response.send_message(
            embed=embed,
            view=DeleteJobView(jobs),
            ephemeral=True,
        )

    @app_commands.command(
        name="работа",
        description="Посмотреть вакансии и подать заявку",
    )
    async def list_jobs(self, interaction: discord.Interaction) -> None:
        jobs = load_jobs()
        embed = build_jobs_embed()

        if not jobs:
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.send_message(
            embed=embed,
            view=ApplyJobView(jobs),
            ephemeral=True,
        )


class BL(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        if self.bot.tree.get_command("bl") is None:
            self.bot.tree.add_command(BLGroup())

    async def cog_load(self) -> None:
        for record in load_ideas():
            if record.get("thread_id"):
                IDEA_DIALOGUE_BY_USER[record["author_id"]] = record["thread_id"]
                IDEA_USER_BY_THREAD[record["thread_id"]] = record["author_id"]
            if record["status"] in IDEA_ACTIVE_STATUSES:
                self.bot.add_view(IdeaApprovalView(self.bot, record))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.content:
            return

        if message.guild is None:
            user_thread_id = IDEA_DIALOGUE_BY_USER.get(message.author.id)
            if user_thread_id is None:
                return

            thread = self.bot.get_channel(user_thread_id)
            if not isinstance(thread, discord.Thread):
                return

            embed = message_relay_embed(message.author, message.content, show_footer=True)
            await thread.send(embed=embed)
            return

        if isinstance(message.channel, discord.Thread):
            user_id = IDEA_USER_BY_THREAD.get(message.channel.id)
            if user_id is None:
                return

            user = await get_user_safe(self.bot, user_id)
            if user is None:
                return
            embed = message_relay_embed(message.author, message.content, show_footer=False)
            try:
                await user.send(embed=embed)
            except discord.Forbidden:
                await message.channel.send(
                    "⚠️ Не удалось доставить сообщение — у автора закрыто ЛС.",
                    delete_after=10,
                )
            return


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BL(bot))