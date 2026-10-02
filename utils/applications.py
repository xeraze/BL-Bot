import json
import uuid
from pathlib import Path

from utils.i18n import DEFAULT_LANG

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
APPLICATIONS_FILE = DATA_DIR / "applications.json"

ACTIVE_STATUSES = frozenset({"new", "reviewing"})


def load_applications() -> list[dict]:
    if not APPLICATIONS_FILE.exists():
        return []
    with open(APPLICATIONS_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_applications(applications: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(APPLICATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(applications, f, ensure_ascii=False, indent=2)


def get_application(app_id: str) -> dict | None:
    for app in load_applications():
        if app["id"] == app_id:
            return app
    return None


def update_application(app_id: str, **fields) -> dict | None:
    applications = load_applications()
    for app in applications:
        if app["id"] == app_id:
            app.update(fields)
            save_applications(applications)
            return app
    return None


def create_application(
    *,
    user_id: int,
    job: dict,
    name_age: str,
    experience: str,
    portfolio: str = "",
    comment: str = "",
    lang: str = DEFAULT_LANG,
) -> dict:
    application = {
        "id": uuid.uuid4().hex[:8],
        "user_id": user_id,
        "lang": lang,
        "job_id": job["id"],
        "job_title": job["title"],
        "job_description": job["description"],
        "job_requirements": job.get("requirements") or job.get("footer", ""),
        "status": "new",
        "message_id": None,
        "channel_id": None,
        "thread_id": None,
        "reviewer_id": None,
        "review_reason": None,
        "name_age": name_age,
        "experience": experience,
        "portfolio": portfolio,
        "comment": comment,
    }
    applications = load_applications()
    applications.append(application)
    save_applications(applications)
    return application


def get_application_by_thread(thread_id: int) -> dict | None:
    for app in load_applications():
        if app.get("thread_id") == thread_id and app["status"] == "reviewing":
            return app
    return None


def get_active_dialogue_by_user(user_id: int) -> dict | None:
    for app in load_applications():
        if (
            app["user_id"] == user_id
            and app["status"] == "reviewing"
            and app.get("thread_id")
        ):
            return app
    return None