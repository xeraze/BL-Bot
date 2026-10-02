"""Локализация бота: словари строк EN (по умолчанию) и RU.

Перевод EN сделан машинно (DeepL) и выверен вручную под терминологию
проекта (application / vacancy / In Review / Accepted / Dialogue).
Использование: t(lang, "key", **fmt); lang = get_lang(interaction).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Union

DEFAULT_LANG = "en"
LANGS = ("en", "ru")
_LANG_NAMES = {"en": "English", "ru": "Русский"}

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "user_langs.json"
_cache: dict[str, str] | None = None


EN = {
    "err.not_configured": "This command is not configured on the server. Please notify an administrator.",
    "err.no_role": "You don't have permission to use this command.",
    "err.check_failed": "A pre-command check did not pass.",
    "err.missing_arg": "Missing required argument: {name}",
    "err.bad_arg": "Invalid argument: {error}",
    "err.generic": "An unexpected error occurred. Administrators have been notified.",
    "errlog.title": "⚠️ Error in command: {command}",
    "errlog.user": "**User:** {name} ({id})",
    "errlog.channel": "**Channel:** {channel}",
    "errlog.field": "📝 Error message",
    "errlog.footer": "Command: /{command}",
    "errlog.unknown_user": "Unknown user",
    "status.new": "New",
    "status.reviewing": "In Review",
    "status.accepted": "Accepted",
    "status.rejected": "Rejected",
    "common.sent_from": "Sent from {guild}",
    "common.accept": "Accept",
    "common.reject": "Reject",
    "common.reviewing": "In Review",
    "common.start_dialogue": "Start dialogue",
    "common.reason_title": "Reason (optional)",
    "common.reason_label": "Reason",
    "common.reason_ph": "State the reason for accepting or rejecting (optional)",
    "jobs.title": "📋 Studio vacancies",
    "jobs.desc": "Below are the open positions in the studio.\nSelect a job from the menu under this message to apply.",
    "jobs.empty": "There are no open vacancies right now. Check back later!",
    "jobs.req_header": "**Requirements:**",
    "jobs.field": "Open vacancies",
    "jobs.field_more": "Open vacancies (continued)",
    "jobs.footer_total": "Total positions: {count}",
    "jobs.footer_shown": " · showing {shown}, remove extras with /vacancy del",
    "news.modal_title": "Publish news",
    "news.label_title": "News title",
    "news.ph_title": "News headline...",
    "news.label_desc": "News description",
    "news.ph_desc": "News text...",
    "news.label_image": "Image (optional)",
    "news.label_pings": "Role pings (optional)",
    "news.bad_link": "The image link must start with `http://` or `https://`.",
    "news.no_channel": "Could not determine the channel to publish to.",
    "news.bad_pings": "Pings must be in `<@&1234>` format, comma-separated, up to 5 roles.",
    "news.too_many_pings": "You can specify at most 5 role pings.",
    "news.publish_fail": "❌ Failed to publish the news in this channel. Check the bot's permissions.",
    "news.published": "✅ News published in the channel.",
    "news.edit_button": "Edit text",
    "news.preview_title": "Publish news",
    "news.preview_desc": "Click the button below to fill in the news fields.\nOnce the form is submitted, the bot will post the embed to this channel.\n\n*Fill in all fields before submitting — the preview does not update automatically.*",
    "idea.decision_fail": "Could not process the decision.",
    "idea.status.new": "New idea",
    "idea.status.reviewing": "In Review",
    "idea.status.accepted": "Accepted",
    "idea.status.rejected": "Rejected",
    "idea.status.dialogue": "Dialogue started",
    "idea.embed_title": "New idea",
    "idea.field_from": "From:",
    "idea.field_status": "Status:",
    "idea.field_reviewer": "Reviewed by:",
    "idea.field_reason": "Reason:",
    "idea.no_permission": "You don't have permission to review ideas.",
    "idea.already_decided": "A decision has already been made for this idea.",
    "idea.need_reviewing": "Put the idea into review first.",
    "idea.thread_fail": "Failed to create the dialogue thread.",
    "idea.thread_name": "Dialogue — idea by {author}",
    "idea.welcome_title": "Dialogue started",
    "idea.welcome_desc": "You have started a dialogue with {reviewer} about their idea.\n\nThe author's DMs will be relayed here, and your messages will be sent to them via DM.",
    "idea.public_author": "From: {name}",
    "idea.reviewing_dm_title": "Your idea has been sent for review",
    "idea.reviewing_dm_desc": "A reviewer has started reviewing your idea. The status will be updated later.",
    "idea.dialogue_dm_title": "Dialogue started on your idea",
    "idea.dialogue_dm_desc": "The reviewer has started a dialogue on your idea. All further communication with the reviewer will happen in this thread. Your messages are logged!",
    "idea.accepted_content": "✅ Idea accepted {mention}.",
    "idea.rejected_content": "✅ Idea rejected {mention}.",
    "idea.accepted_title": "Your idea has been accepted",
    "idea.rejected_title": "Your idea has been rejected",
    "idea.accepted_desc": "Your idea has been accepted. Thanks for your contribution!",
    "idea.rejected_desc": "Your idea has been rejected. Send other ideas — we're always happy to hear new suggestions!",
    "idea.reviewed_by": "Reviewed by: {name}",
    "idea.sent": "✅ Your idea has been sent for review. Please wait for a response.",
    "idea.no_channel": "The idea review channel is not configured. Please contact STAFF.",
    "idea.channel_missing": "The idea review channel was not found. Please contact STAFF.",
    "idea.empty": "The idea text cannot be empty.",
    "idea.relay_dm_closed": "⚠️ Failed to deliver the message — the author has DMs closed.",
    "vadd.modal_title": "Add vacancy",
    "vadd.label_title": "Job title",
    "vadd.ph_title": "E.g.: Developer, Designer, etc.",
    "vadd.label_desc": "Job description",
    "vadd.ph_desc": "Responsibilities, conditions, what the job involves...",
    "vadd.label_req": "Requirements",
    "vadd.ph_req": "Experience, skills, what's needed from the candidate...",
    "vadd.added": "✅ Vacancy **{title}** added to the list.",
    "apply.modal_title": "Application: {title}",
    "apply.label_name_age": "Name and age",
    "apply.ph_name_age": "E.g.: Alexey, 18 years old",
    "apply.label_experience": "Experience",
    "apply.ph_experience": "Tell us about your experience in this field...",
    "apply.label_portfolio": "Portfolio / contacts",
    "apply.ph_portfolio": "Links to your work, Discord, Telegram...",
    "apply.label_comment": "Comment (optional)",
    "apply.ph_comment": "Why do you want to join us, extra info...",
    "apply.select_ph": "Choose a job to apply for",
    "apply.no_channel": "The applications channel is not configured. Please contact STAFF.",
    "apply.channel_missing": "The applications channel was not found. Please contact STAFF.",
    "apply.sent": "✅ Your application for **{title}** has been sent. Please wait for a response.",
    "vdel.select_ph": "Choose a vacancy to remove",
    "vdel.not_found": "The vacancy was already removed or not found. Refresh the list and try again.",
    "vdel.removed": "🗑️ Vacancy **{title}** removed from the list.",
    "vdel.empty": "The vacancy list is empty — nothing to remove.",
    "vdel.embed_title": "Remove a vacancy",
    "vdel.embed_desc": "Pick the position from the list below to remove.",
    "lang.current": "Current language: {language}",
    "lang.hint": "Switch language: `/lang en` or `/lang ru`.",
    "lang.changed": "✅ Bot language switched to {language}.",
    "app.embed_title": "📩 Application: {job}",
    "app.candidate": "**Candidate:** {mention} (`{id}`)",
    "app.status_line": "**Status:** `{label}`",
    "app.name_age_line": "**Name and age:** {value}",
    "app.field_experience": "Experience",
    "app.field_portfolio": "Portfolio / contacts",
    "app.field_comment": "Comment",
    "app.field_job_desc": "Job description",
    "app.field_job_req": "Job requirements",
    "app.id_footer": "Application ID: {id}",
    "app.action_ph": "Application actions",
    "app.no_permission": "You don't have permission to review applications.",
    "app.not_found": "Application not found.",
    "app.update_fail": "Failed to update the application.",
    "app.status_updated": "Application status updated: `{label}`.",
    "app.dialogue_started": "Dialogue with the candidate has started.",
    "app.dm_status_title": "Your application status has changed",
    "app.dm_status_desc": "The status of your application for **{job}** has been changed to `{label}`",
    "app.changed_by": "Changed by: {name}",
    "app.dm_dialogue_title": "Dialogue started — {job}",
    "app.dm_dialogue_desc": "Reviewer {reviewer} has started a **dialogue** with you.\n\nThe reviewer sees all the messages you send the bot via DM.",
    "app.thread_name": "Dialogue — {job}",
    "app.welcome_title": "Dialogue with the candidate",
    "app.welcome_desc": "Reviewer: {reviewer}\nCandidate: {candidate}\n\nWrite in this thread — messages are delivered to the candidate via DM.\nThe candidate's DM replies to the bot will appear here too.",
    "app.relay_dm_closed": "⚠️ Failed to deliver the message — the candidate has DMs closed.",
}

RU = {
    "err.not_configured": "Эта команда не настроена на сервере. Сообщите администратору.",
    "err.no_role": "У вас нет прав для использования этой команды.",
    "err.check_failed": "Проверка перед выполнением команды не пройдена.",
    "err.missing_arg": "Отсутствует обязательный аргумент: {name}",
    "err.bad_arg": "Неправильно указан аргумент: {error}",
    "err.generic": "Произошла непредвиденная ошибка. Администраторы уведомлены.",
    "errlog.title": "⚠️ Ошибка в команде: {command}",
    "errlog.user": "**Пользователь:** {name} ({id})",
    "errlog.channel": "**Канал:** {channel}",
    "errlog.field": "📝 Сообщение об ошибке",
    "errlog.footer": "Команда: /{command}",
    "errlog.unknown_user": "Неизвестный пользователь",
    "status.new": "Новая",
    "status.reviewing": "На рассмотрении",
    "status.accepted": "Принята",
    "status.rejected": "Отклонена",
    "common.sent_from": "Отправлено с {guild}",
    "common.accept": "Принять",
    "common.reject": "Отклонить",
    "common.reviewing": "На рассмотрении",
    "common.start_dialogue": "Начать диалог",
    "common.reason_title": "Причина (необязательно)",
    "common.reason_label": "Причина",
    "common.reason_ph": "Укажите причину принятия или отклонения (необязательно)",
    "jobs.title": "📋 Вакансии студии",
    "jobs.desc": "Ниже — открытые позиции в студии.\nВыберите должность в меню под сообщением, чтобы подать заявку.",
    "jobs.empty": "На данный момент открытых вакансий нет. Загляните позже!",
    "jobs.req_header": "**Требования:**",
    "jobs.field": "Открытые вакансии",
    "jobs.field_more": "Открытые вакансии (продолжение)",
    "jobs.footer_total": "Всего позиций: {count}",
    "jobs.footer_shown": " · показано {shown}, уберите лишние через /vacancy del",
    "news.modal_title": "Публикация новости",
    "news.label_title": "Название новости",
    "news.ph_title": "Заголовок новости...",
    "news.label_desc": "Описание новости",
    "news.ph_desc": "Текст новости...",
    "news.label_image": "Изображение (необязательно)",
    "news.label_pings": "Пинги ролей (необязательно)",
    "news.bad_link": "Ссылка на изображение должна начинаться с `http://` или `https://`.",
    "news.no_channel": "Не удалось определить канал для публикации.",
    "news.bad_pings": "Пинги должны быть в формате `<@&1234>` через запятую, до 5 ролей.",
    "news.too_many_pings": "Можно указать не более 5 пинг ролей.",
    "news.publish_fail": "❌ Не удалось опубликовать новость в этом канале. Проверьте права бота.",
    "news.published": "✅ Новость опубликована в канал.",
    "news.edit_button": "Изменить текст",
    "news.preview_title": "Публикация новости",
    "news.preview_desc": "Нажмите кнопку ниже, чтобы заполнить поля новости.\nПосле отправки формы бот опубликует эмбед в этот канал.\n\n*Заполните все поля перед отправкой — предпросмотр не обновляется автоматически.*",
    "idea.decision_fail": "Не удалось обработать решение.",
    "idea.status.new": "Новая идея",
    "idea.status.reviewing": "На рассмотрении",
    "idea.status.accepted": "Принята",
    "idea.status.rejected": "Отклонена",
    "idea.status.dialogue": "Диалог начат",
    "idea.embed_title": "Новая идея",
    "idea.field_from": "От:",
    "idea.field_status": "Статус:",
    "idea.field_reviewer": "Выполнил:",
    "idea.field_reason": "Причина:",
    "idea.no_permission": "У вас нет прав для проверки идей.",
    "idea.already_decided": "По этой идее уже принято решение.",
    "idea.need_reviewing": "Сначала поставьте идею на рассмотрение.",
    "idea.thread_fail": "Не удалось создать ветку диалога.",
    "idea.thread_name": "Диалог — идея от {author}",
    "idea.welcome_title": "Начат диалог",
    "idea.welcome_desc": "Вы начали диалог с {reviewer} по его идее.\n\nСообщения автора из ЛС будут приходить сюда, ваши сообщения будут отправляться пользователю в ЛС.",
    "idea.public_author": "От: {name}",
    "idea.reviewing_dm_title": "Ваша идея отправлена на рассмотрение",
    "idea.reviewing_dm_desc": "Проверяющий начал рассматривать вашу идею. Статус будет обновлён позже.",
    "idea.dialogue_dm_title": "Начат диалог по вашей идее",
    "idea.dialogue_dm_desc": "Проверяющий начал диалог по вашей идее. Всё дальнейшее взаимодействие с проверяющим будет происходить в этой ветке. Ваши сообщения логгируются!",
    "idea.accepted_content": "✅ Идея принята {mention}.",
    "idea.rejected_content": "✅ Идея отклонена {mention}.",
    "idea.accepted_title": "Ваша идея принята",
    "idea.rejected_title": "Ваша идея отклонена",
    "idea.accepted_desc": "Ваша идея принята. Спасибо за ваш вклад!",
    "idea.rejected_desc": "Ваша идея отклонена. Присылайте другие идеи, мы всегда рады новым предложениям!",
    "idea.reviewed_by": "Проверил: {name}",
    "idea.sent": "✅ Ваша идея отправлена на рассмотрение. Ожидайте ответа.",
    "idea.no_channel": "Канал для проверки идей не настроен. Сообщите STAFF.",
    "idea.channel_missing": "Канал для проверки идей не найден. Сообщите STAFF.",
    "idea.empty": "Текст идеи не может быть пустым.",
    "idea.relay_dm_closed": "⚠️ Не удалось доставить сообщение — у автора закрыто ЛС.",
    "vadd.modal_title": "Добавление вакансии",
    "vadd.label_title": "Название должности",
    "vadd.ph_title": "Например: Разработчик, Дизайнер и т.д",
    "vadd.label_desc": "Описание должности",
    "vadd.ph_desc": "Обязанности, условия, что предстоит делать...",
    "vadd.label_req": "Требования",
    "vadd.ph_req": "Опыт, навыки, что нужно от кандидата...",
    "vadd.added": "✅ Вакансия **{title}** добавлена в список.",
    "apply.modal_title": "Заявка: {title}",
    "apply.label_name_age": "Имя и возраст",
    "apply.ph_name_age": "Например: Алексей, 18 лет",
    "apply.label_experience": "Опыт",
    "apply.ph_experience": "Расскажите о своём опыте в данной сфере...",
    "apply.label_portfolio": "Портфолио / контакты",
    "apply.ph_portfolio": "Ссылки на работы, Discord, Telegram...",
    "apply.label_comment": "Комментарий (необязательно)",
    "apply.ph_comment": "Почему хотите к нам, дополнительная информация...",
    "apply.select_ph": "Выберите должность для подачи заявки",
    "apply.no_channel": "Канал для заявок не настроен. Сообщите STAFF.",
    "apply.channel_missing": "Канал для заявок не найден. Сообщите STAFF.",
    "apply.sent": "✅ Заявка на должность **{title}** отправлена. Ожидайте ответа.",
    "vdel.select_ph": "Выберите вакансию для удаления",
    "vdel.not_found": "Вакансия уже была удалена или не найдена. Обновите список и попробуйте снова.",
    "vdel.removed": "🗑️ Вакансия **{title}** удалена из списка.",
    "vdel.empty": "Список вакансий пуст — удалять нечего.",
    "vdel.embed_title": "Удаление вакансии",
    "vdel.embed_desc": "Выберите должность из списка ниже, которую нужно убрать.",
    "lang.current": "Текущий язык: {language}",
    "lang.hint": "Сменить язык: `/lang en` или `/lang ru`.",
    "lang.changed": "✅ Язык бота переключён: {language}.",
    "app.embed_title": "📩 Заявка: {job}",
    "app.candidate": "**Кандидат:** {mention} (`{id}`)",
    "app.status_line": "**Статус:** `{label}`",
    "app.name_age_line": "**Имя и возраст:** {value}",
    "app.field_experience": "Опыт",
    "app.field_portfolio": "Портфолио / контакты",
    "app.field_comment": "Комментарий",
    "app.field_job_desc": "Описание должности",
    "app.field_job_req": "Требования к должности",
    "app.id_footer": "ID заявки: {id}",
    "app.action_ph": "Действие с заявкой",
    "app.no_permission": "У вас нет прав для проверки заявок.",
    "app.not_found": "Заявка не найдена.",
    "app.update_fail": "Не удалось обновить заявку.",
    "app.status_updated": "Статус заявки обновлён: `{label}`.",
    "app.dialogue_started": "Диалог с кандидатом начат.",
    "app.dm_status_title": "Статус вашей заявки изменён",
    "app.dm_status_desc": "Статус вашей заявки **{job}** изменён на `{label}`",
    "app.changed_by": "Изменил: {name}",
    "app.dm_dialogue_title": "Начат диалог — {job}",
    "app.dm_dialogue_desc": "Проверяющий {reviewer} начал с вами **диалог**.\n\nВсе сообщения, которые вы пишете боту в ЛС — видит проверяющий.",
    "app.thread_name": "Диалог — {job}",
    "app.welcome_title": "Диалог с кандидатом",
    "app.welcome_desc": "Проверяющий: {reviewer}\nКандидат: {candidate}\n\nПишите в эту ветку — сообщения придут кандидату в ЛС.\nОтветы кандидата в ЛС боту тоже появятся здесь.",
    "app.relay_dm_closed": "⚠️ Не удалось доставить сообщение — у кандидата закрыты ЛС.",
}

_STRINGS = {"en": EN, "ru": RU}


def lang_name(lang: str) -> str:
    """Название языка на самом языке (для /lang)."""
    return _LANG_NAMES.get(lang, lang)


def t(lang: str, key: str, **fmt) -> str:
    """Перевод ключа; fallback en -> ru -> сам ключ (никогда не падает)."""
    table = _STRINGS.get(lang) or _STRINGS[DEFAULT_LANG]
    template = table.get(key)
    if template is None:
        template = _STRINGS[DEFAULT_LANG].get(key) or _STRINGS["ru"].get(key)
    if template is None:
        template = key
    try:
        return template.format(**fmt)
    except (KeyError, IndexError, ValueError):
        return template


def _load() -> dict[str, str]:
    global _cache
    if _cache is None:
        _cache = {}
        try:
            if _DATA_FILE.exists():
                with open(_DATA_FILE, encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    _cache = {str(k): str(v) for k, v in raw.items() if str(v) in LANGS}
        except (OSError, ValueError):
            _cache = {}
    return _cache


def get_lang(user: Union[int, str, object, None] = None) -> str:
    """Язык пользователя: сохранённый выбор -> язык по умолчанию.

    Принимает user_id, объект с атрибутом .user (Interaction) или None.
    """
    uid: int | None = None
    if isinstance(user, int):
        uid = user
    elif user is not None and hasattr(user, "user"):
        uid = getattr(user.user, "id", None)
    if uid is not None:
        lang = _load().get(str(uid))
        if lang in LANGS:
            return lang
    return DEFAULT_LANG


def set_lang(user_id: int, lang: str) -> None:
    """Сохранить выбор языка пользователя (data/user_langs.json)."""
    if lang not in LANGS:
        raise ValueError(f"unknown language: {language}")
    prefs = _load()
    prefs[str(user_id)] = lang
    _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)


def coerce_lang(value: object) -> str:
    """Валидный язык из записи (application/idea) или язык по умолчанию."""
    return value if isinstance(value, str) and value in LANGS else DEFAULT_LANG


def status_label(status: str, lang: str) -> str:
    """Метка статуса заявки (applications) по ключу status.*."""
    return t(lang, f"status.{status}")
