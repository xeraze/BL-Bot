import json
import uuid
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
IDEAS_FILE = DATA_DIR / "ideas.json"

IDEA_ACTIVE_STATUSES = frozenset({"new", "reviewing", "dialogue"})


def load_ideas() -> list[dict]:
    if not IDEAS_FILE.exists():
        return []
    with open(IDEAS_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_ideas(ideas: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(IDEAS_FILE, "w", encoding="utf-8") as f:
        json.dump(ideas, f, ensure_ascii=False, indent=2)


def save_idea(record: dict) -> None:
    ideas = load_ideas()
    for i, idea in enumerate(ideas):
        if idea["id"] == record["id"]:
            ideas[i] = record
            break
    else:
        ideas.append(record)
    save_ideas(ideas)


def create_idea(
    *,
    author_id: int,
    author_name: str,
    author_avatar: str,
    text: str,
) -> dict:
    record = {
        "id": uuid.uuid4().hex[:8],
        "author_id": author_id,
        "author_name": author_name,
        "author_avatar": author_avatar,
        "text": text,
        "status": "new",
        "reviewer_id": None,
        "reviewer_name": None,
        "review_reason": None,
        "channel_id": None,
        "message_id": None,
        "thread_id": None,
        "decision_made": False,
    }
    save_idea(record)
    return record
