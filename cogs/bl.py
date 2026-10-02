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
from utils.i18n import (
    DEFAULT_LANG,
    coerce_lang,
    get_lang,
    lang_name,
    set_lang,
    t,
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


def format_job_block(index: int, job: dict, lang: str = DEFAULT_LANG) -> str:
    requirements = _job_requirements(job)
    block = f"**{index}. {job['title']}**\n{job['description']}"
    if requirements:
        block += f"\n\n{t(lang, 'jobs.req_header')}\n{requirements}"
    return block


def _split_text(text: str, limit: int = MAX_EMBED_FIELD) -> list[str]:
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def build_jobs_embed(lang: str = DEFAULT_LANG) -> discord.Embed:
    jobs = load_jobs()

    embed = base_embed(
        title=t(lang, "jobs.title"),
        description=t(lang, "jobs.desc"),
    )

    if not jobs:
        embed.description = t(lang, "jobs.empty")
        return embed

    head_chars = len(embed.title) + len(embed.description)
    fields: list[str] = []
    current = ""
    shown = 0
    stopped = False

    for index, job in enumerate(jobs, start=1):
        for part in _split_text(format_job_block(index, job, lang)):
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
        name = (
            t(lang, "jobs.field")
            if position == 0
            else t(lang, "jobs.field_more")
        )
        embed.add_field(name=name, value=value, inline=False)

    footer = t(lang, "jobs.footer_total", count=len(jobs))
    if shown < len(jobs):
        footer += t(lang, "jobs.footer_shown", shown=shown)
    embed.set_footer(text=footer)
    return embed


class NewsModal(discord.ui.Modal, title="Publish news"):
    title_input = discord.ui.TextInput(
        label="News title",
        placeholder="News headline...",
        max_length=256,
        required=True,
    )
    description_input = discord.ui.TextInput(
        label="News description",
        placeholder="News text...",
        style=discord.TextStyle.paragraph,
        max_length=4000,
        required=True,
    )
    image_input = discord.ui.TextInput(
        label="Image (optional)",
        placeholder="https://example.com/image.png",
        required=False,
        max_length=500,
    )
    pings_input = discord.ui.TextInput(
        label="Role pings (optional)",
        placeholder="<@&1234>, <@&5678>",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=200,
    )

    def __init__(self, lang: str = DEFAULT_LANG) -> None:
        super().__init__(title=t(lang, "news.modal_title"))
        self.lang = lang
        self.title_input.label = t(lang, "news.label_title")
        self.title_input.placeholder = t(lang, "news.ph_title")
        self.description_input.label = t(lang, "news.label_desc")
        self.description_input.placeholder = t(lang, "news.ph_desc")
        self.image_input.label = t(lang, "news.label_image")
        self.pings_input.label = t(lang, "news.label_pings")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        lang = self.lang
        embed = base_embed(
            title=self.title_input.value,
            description=self.description_input.value,
        )

        image_url = self.image_input.value.strip()
        if image_url:
            if not image_url.startswith(("http://", "https://")):
                await interaction.response.send_message(
                    t(lang, "news.bad_link"),
                    ephemeral=True,
                )
                return
            embed.set_image(url=image_url)

        if interaction.channel is None:
            await interaction.response.send_message(
                t(lang, "news.no_channel"),
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
                        t(lang, "news.bad_pings"),
                        ephemeral=True,
                    )
                    return
                mentions.append(match.group(1))

            mentions = list(dict.fromkeys(mentions))
            if len(mentions) > 5:
                await interaction.response.send_message(
                    t(lang, "news.too_many_pings"),
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
                t(lang, "news.publish_fail"),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            t(lang, "news.published"),
            ephemeral=True,
        )


class NewsEditButton(discord.ui.Button):
    def __init__(self, lang: str = DEFAULT_LANG) -> None:
        super().__init__(
            label=t(lang, "news.edit_button"),
            style=discord.ButtonStyle.primary,
            emoji="🎨",
        )
        self.lang = lang

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(NewsModal(self.lang))


class NewsPreviewView(discord.ui.View):
    def __init__(self, lang: str = DEFAULT_LANG) -> None:
        super().__init__(timeout=300)
        self.add_item(NewsEditButton(lang))


class IdeaStatusReasonModal(discord.ui.Modal, title="Reason (optional)"):
    reason = discord.ui.TextInput(
        label="Reason",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000,
        placeholder="State the reason for accepting or rejecting (optional)",
    )

    def __init__(
        self,
        idea_view: "IdeaApprovalView",
        action: str,
        lang: str = DEFAULT_LANG,
    ) -> None:
        super().__init__(title=t(lang, "common.reason_title"))
        self.lang = lang
        self.reason.label = t(lang, "common.reason_label")
        self.reason.placeholder = t(lang, "common.reason_ph")
        self.idea_view = idea_view
        self.action = action

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if self.idea_view is None:
            await interaction.response.send_message(
                t(get_lang(interaction), "idea.decision_fail"),
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
                t(get_lang(interaction), "idea.decision_fail"),
                ephemeral=True,
            )
            return

        await view.process_decision(interaction, self.action)


class IdeaApprovalView(discord.ui.View):
    STATUS_KEYS = frozenset(
        {"new", "reviewing", "accepted", "rejected", "dialogue"}
    )

    def __init__(
        self,
        bot: discord.Client,
        record: dict,
        lang: str = DEFAULT_LANG,
    ) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.record = record
        self.lang = lang
        self._rebuild_buttons()

    @property
    def idea_id(self) -> str:
        return self.record["id"]

    @property
    def idea_text(self) -> str:
        return self.record["text"]

    def status_label(self, lang: str) -> str:
        status = self.record["status"]
        return (
            t(lang, f"idea.status.{status}")
            if status in self.STATUS_KEYS
            else status
        )

    def _rebuild_buttons(self) -> None:
        lang = self.lang
        self.clear_items()
        status = self.record["status"]
        if status == "new":
            self.add_item(IdeaReviewButton(self.idea_id, t(lang, "common.accept"), discord.ButtonStyle.success, "accept"))
            self.add_item(IdeaReviewButton(self.idea_id, t(lang, "common.reject"), discord.ButtonStyle.danger, "reject"))
            self.add_item(IdeaReviewButton(self.idea_id, t(lang, "common.reviewing"), discord.ButtonStyle.secondary, "reviewing"))
        else:
            self.add_item(IdeaReviewButton(self.idea_id, t(lang, "common.accept"), discord.ButtonStyle.success, "accept"))
            self.add_item(IdeaReviewButton(self.idea_id, t(lang, "common.reject"), discord.ButtonStyle.danger, "reject"))
            dialogue = IdeaReviewButton(self.idea_id, t(lang, "common.start_dialogue"), discord.ButtonStyle.secondary, "dialogue")
            dialogue.disabled = status != "reviewing"
            self.add_item(dialogue)
        if self.record.get("decision_made"):
            self.disable_all_items()

    def _save(self) -> None:
        save_idea(self.record)

    def disable_all_items(self) -> None:
        for item in self.children:
            item.disabled = True

    def build_embed(self, lang: str | None = None) -> discord.Embed:
        lang = self.lang if lang is None else lang
        embed = base_embed(
            title=t(lang, "idea.embed_title"),
            description=self.idea_text[:4096],
        )
        embed.add_field(
            name=t(lang, "idea.field_from"),
            value=f"<@{self.record['author_id']}>",
            inline=False,
        )
        embed.add_field(
            name=t(lang, "idea.field_status"),
            value=self.status_label(lang),
            inline=False,
        )
        if self.record.get("reviewer_id"):
            embed.add_field(
                name=t(lang, "idea.field_reviewer"),
                value=f"<@{self.record['reviewer_id']}>",
                inline=False,
            )
        if self.record.get("review_reason"):
            embed.add_field(
                name=t(lang, "idea.field_reason"),
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
        lang = get_lang(interaction)
        self.lang = lang

        if not isinstance(interaction.user, discord.Member) or not member_has_role(
            interaction.user, "IDEA_APPROVER_ROLE_ID"
        ):
            await interaction.response.send_message(
                t(lang, "idea.no_permission"),
                ephemeral=True,
            )
            return

        if self.record.get("decision_made"):
            await interaction.response.send_message(
                t(lang, "idea.already_decided"),
                ephemeral=True,
            )
            return

        if action in ("accept", "reject") and reason is None and not reason_collected:
            await interaction.response.send_modal(IdeaStatusReasonModal(self, action, lang))
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
            await self._finalize_decision(interaction, accepted=True, lang=lang)
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
            await self._finalize_decision(interaction, accepted=False, lang=lang)
            return

        if action == "reviewing":
            self.record.update(
                status="reviewing",
                reviewer_id=interaction.user.id,
                reviewer_name=interaction.user.display_name,
            )
            self._save()
            self._rebuild_buttons()
            await interaction.response.edit_message(embed=self.build_embed(lang), view=self)
            author_lang = coerce_lang(self.record.get("lang"))
            await self._notify_author(
                interaction.client,
                t(author_lang, "idea.reviewing_dm_title"),
                t(author_lang, "idea.reviewing_dm_desc"),
                interaction.guild,
            )
            return

        if action == "dialogue":
            if self.record["status"] != "reviewing":
                await interaction.response.send_message(
                    t(lang, "idea.need_reviewing"),
                    ephemeral=True,
                )
                return
            thread = await self._create_dialogue_thread(interaction, lang)
            if thread is None:
                await interaction.response.send_message(
                    t(lang, "idea.thread_fail"),
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
            await interaction.response.edit_message(embed=self.build_embed(lang), view=self)
            author_lang = coerce_lang(self.record.get("lang"))
            await self._notify_author(
                interaction.client,
                t(author_lang, "idea.dialogue_dm_title"),
                t(author_lang, "idea.dialogue_dm_desc"),
                interaction.guild,
            )
            return

    async def _create_dialogue_thread(
        self,
        interaction: discord.Interaction,
        lang: str = DEFAULT_LANG,
    ) -> discord.Thread | None:
        if interaction.message is None:
            return None

        try:
            thread_name = t(
                lang, "idea.thread_name", author=self.record["author_name"]
            )[:100]
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
            title=t(lang, "idea.welcome_title"),
            description=t(
                lang, "idea.welcome_desc", reviewer=interaction.user.mention
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

        lang = coerce_lang(self.record.get("lang"))
        public_embed = base_embed(
            title=t(lang, "idea.embed_title"),
            description=self.idea_text[:4096],
        )
        public_embed.set_author(
            name=t(lang, "idea.public_author", name=self.record["author_name"]),
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
        lang: str = DEFAULT_LANG,
    ) -> None:
        content_key = "idea.accepted_content" if accepted else "idea.rejected_content"
        await interaction.response.edit_message(
            content=t(lang, content_key, mention=interaction.user.mention),
            embed=self.build_embed(lang),
            view=self,
        )
        author_lang = coerce_lang(self.record.get("lang"))
        title = t(
            author_lang,
            "idea.accepted_title" if accepted else "idea.rejected_title",
        )
        description = t(
            author_lang,
            "idea.accepted_desc" if accepted else "idea.rejected_desc",
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
        lang = coerce_lang(self.record.get("lang"))
        embed = base_embed(title=title, description=description)
        if self.record.get("review_reason"):
            embed.add_field(
                name=t(lang, "idea.field_reason"),
                value=self.record["review_reason"][:1024],
                inline=False,
            )
        if self.record.get("reviewer_name"):
            embed.set_footer(
                text=t(lang, "idea.reviewed_by", name=self.record["reviewer_name"])
            )
        view = None
        if guild is not None:
            view = discord.ui.View(timeout=None)
            view.add_item(
                discord.ui.Button(
                    label=t(lang, "common.sent_from", guild=guild.name),
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


class AddJobModal(discord.ui.Modal, title="Add vacancy"):
    title_input = discord.ui.TextInput(
        label="Job title",
        placeholder="E.g.: Developer, Designer, etc.",
        max_length=100,
        required=True,
    )
    description_input = discord.ui.TextInput(
        label="Job description",
        placeholder="Responsibilities, conditions, what the job involves...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )
    requirements_input = discord.ui.TextInput(
        label="Requirements",
        placeholder="Experience, skills, what's needed from the candidate...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    def __init__(self, lang: str = DEFAULT_LANG) -> None:
        super().__init__(title=t(lang, "vadd.modal_title"))
        self.lang = lang
        self.title_input.label = t(lang, "vadd.label_title")
        self.title_input.placeholder = t(lang, "vadd.ph_title")
        self.description_input.label = t(lang, "vadd.label_desc")
        self.description_input.placeholder = t(lang, "vadd.ph_desc")
        self.requirements_input.label = t(lang, "vadd.label_req")
        self.requirements_input.placeholder = t(lang, "vadd.ph_req")

    async def on_submit(self, interaction: discord.Interaction) -> None:
        job = add_job(
            title=self.title_input.value,
            description=self.description_input.value,
            requirements=self.requirements_input.value,
        )
        await interaction.response.send_message(
            t(self.lang, "vadd.added", title=job["title"]),
            ephemeral=True,
        )


class JobApplicationModal(discord.ui.Modal):
    def __init__(self, job: dict, lang: str = DEFAULT_LANG) -> None:
        empty_title = t(lang, "apply.modal_title", title="")
        title_slot = max(1, 45 - len(empty_title))
        super().__init__(title=t(lang, "apply.modal_title", title=job["title"][:title_slot]))
        self.job = job
        self.lang = lang

        self.name_age = discord.ui.TextInput(
            label=t(lang, "apply.label_name_age"),
            placeholder=t(lang, "apply.ph_name_age"),
            max_length=100,
            required=True,
        )
        self.experience = discord.ui.TextInput(
            label=t(lang, "apply.label_experience"),
            placeholder=t(lang, "apply.ph_experience"),
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True,
        )
        self.portfolio = discord.ui.TextInput(
            label=t(lang, "apply.label_portfolio"),
            placeholder=t(lang, "apply.ph_portfolio"),
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False,
        )
        self.comment = discord.ui.TextInput(
            label=t(lang, "apply.label_comment"),
            placeholder=t(lang, "apply.ph_comment"),
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False,
        )

        self.add_item(self.name_age)
        self.add_item(self.experience)
        self.add_item(self.portfolio)
        self.add_item(self.comment)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        lang = self.lang
        channel_id = get_applications_channel_id()
        if channel_id is None:
            await interaction.response.send_message(
                t(lang, "apply.no_channel"),
                ephemeral=True,
            )
            return

        channel = interaction.client.get_channel(channel_id)
        if channel is None:
            await interaction.response.send_message(
                t(lang, "apply.channel_missing"),
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
            lang=lang,
        )

        embed = build_application_embed(application, interaction.user, lang)
        review_view = ApplicationReviewView(application["id"], "new")
        interaction.client.add_view(review_view)
        message = await channel.send(embed=embed, view=review_view)

        update_application(
            application["id"],
            message_id=message.id,
            channel_id=channel.id,
        )

        await interaction.response.send_message(
            t(lang, "apply.sent", title=job["title"]),
            ephemeral=True,
        )


class ApplyJobSelect(discord.ui.Select):
    def __init__(self, jobs: list[dict], lang: str = DEFAULT_LANG) -> None:
        options = [
            discord.SelectOption(
                label=job["title"][:100],
                description=job["description"][:100] or None,
                value=job["id"],
            )
            for job in jobs[:25]
        ]
        super().__init__(
            placeholder=t(lang, "apply.select_ph"),
            options=options,
            min_values=1,
            max_values=1,
        )
        self.jobs = {job["id"]: job for job in jobs}

    async def callback(self, interaction: discord.Interaction) -> None:
        job = self.jobs[self.values[0]]
        await interaction.response.send_modal(
            JobApplicationModal(job, get_lang(interaction))
        )


class ApplyJobView(discord.ui.View):
    def __init__(self, jobs: list[dict], lang: str = DEFAULT_LANG) -> None:
        super().__init__(timeout=300)
        self.add_item(ApplyJobSelect(jobs, lang))


class DeleteJobSelect(discord.ui.Select):
    def __init__(self, jobs: list[dict], lang: str = DEFAULT_LANG) -> None:
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
            placeholder=t(lang, "vdel.select_ph"),
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        lang = get_lang(interaction)
        job_id = self.values[0]
        removed = remove_job(job_id)

        if removed is None:
            await interaction.response.send_message(
                t(lang, "vdel.not_found"),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            t(lang, "vdel.removed", title=removed["title"]),
            ephemeral=True,
        )


class DeleteJobView(discord.ui.View):
    def __init__(self, jobs: list[dict], lang: str = DEFAULT_LANG) -> None:
        super().__init__(timeout=300)
        self.add_item(DeleteJobSelect(jobs, lang))


class BL(commands.Cog):
    """Команды студии BL."""

    vacancy = app_commands.Group(
        name="vacancy",
        description="Manage studio vacancies",
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @vacancy.command(
        name="add",
        description="Add a vacancy to the list (not published)",
    )
    @has_role("ROLE_JOBS_MANAGE")
    async def vacancy_add(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(AddJobModal(get_lang(interaction)))

    @vacancy.command(
        name="del",
        description="Remove a vacancy from the list",
    )
    @has_role("ROLE_JOBS_MANAGE")
    async def vacancy_del(self, interaction: discord.Interaction) -> None:
        lang = get_lang(interaction)
        jobs = load_jobs()

        if not jobs:
            await interaction.response.send_message(
                t(lang, "vdel.empty"),
                ephemeral=True,
            )
            return

        embed = base_embed(
            title=t(lang, "vdel.embed_title"),
            description=t(lang, "vdel.embed_desc"),
        )
        await interaction.response.send_message(
            embed=embed,
            view=DeleteJobView(jobs, lang),
            ephemeral=True,
        )

    @app_commands.command(
        name="post",
        description="Publish a news post in this channel",
    )
    @has_role("ROLE_NEWS")
    async def post(self, interaction: discord.Interaction) -> None:
        lang = get_lang(interaction)
        preview = base_embed(
            title=t(lang, "news.preview_title"),
            description=t(lang, "news.preview_desc"),
        )
        await interaction.response.send_message(
            embed=preview,
            view=NewsPreviewView(lang),
            ephemeral=True,
        )

    @app_commands.command(
        name="idea",
        description="Submit an idea for review",
    )
    @app_commands.describe(idea="Idea text")
    async def idea(self, interaction: discord.Interaction, idea: str) -> None:
        lang = get_lang(interaction)
        review_channel_id = get_idea_review_channel_id()
        if review_channel_id is None:
            await interaction.response.send_message(
                t(lang, "idea.no_channel"),
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
                t(lang, "idea.channel_missing"),
                ephemeral=True,
            )
            return

        idea_text = idea.strip()
        if not idea_text:
            await interaction.response.send_message(
                t(lang, "idea.empty"),
                ephemeral=True,
            )
            return

        record = create_idea(
            author_id=interaction.user.id,
            author_name=interaction.user.display_name,
            author_avatar=interaction.user.display_avatar.url,
            text=idea_text,
            lang=lang,
        )
        view = IdeaApprovalView(interaction.client, record, lang)
        message = await review_channel.send(embed=view.build_embed(lang), view=view)
        record.update(channel_id=review_channel.id, message_id=message.id)
        save_idea(record)

        await interaction.response.send_message(
            t(lang, "idea.sent"),
            ephemeral=True,
        )

    @app_commands.command(
        name="vacancies",
        description="View vacancies and apply",
    )
    async def vacancies(self, interaction: discord.Interaction) -> None:
        lang = get_lang(interaction)
        jobs = load_jobs()
        embed = build_jobs_embed(lang)

        if not jobs:
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.send_message(
            embed=embed,
            view=ApplyJobView(jobs, lang),
            ephemeral=True,
        )

    @app_commands.command(
        name="lang",
        description="Show or change the bot language",
    )
    @app_commands.describe(lang="Language to switch to (omit to show the current one)")
    @app_commands.choices(
        lang=[
            app_commands.Choice(name="English", value="en"),
            app_commands.Choice(name="Русский", value="ru"),
        ]
    )
    async def lang_cmd(
        self, interaction: discord.Interaction, lang: str | None = None
    ) -> None:
        if lang is None:
            current = get_lang(interaction)
            await interaction.response.send_message(
                t(current, "lang.current", language=lang_name(current))
                + "\n"
                + t(current, "lang.hint"),
                ephemeral=True,
            )
            return

        set_lang(interaction.user.id, lang)
        await interaction.response.send_message(
            t(lang, "lang.changed", language=lang_name(lang)),
            ephemeral=True,
        )

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
                    t(DEFAULT_LANG, "idea.relay_dm_closed"),
                    delete_after=10,
                )
            return


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BL(bot))