import json
import uuid
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
JOBS_FILE = DATA_DIR / "jobs.json"


def load_jobs() -> list[dict]:
    if not JOBS_FILE.exists():
        return []
    with open(JOBS_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_jobs(jobs: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)


def add_job(title: str, description: str, requirements: str) -> dict:
    job = {
        "id": uuid.uuid4().hex[:8],
        "title": title,
        "description": description,
        "requirements": requirements,
    }
    jobs = load_jobs()
    jobs.append(job)
    save_jobs(jobs)
    return job


def remove_job(job_id: str) -> dict | None:
    jobs = load_jobs()
    for i, job in enumerate(jobs):
        if job["id"] == job_id:
            removed = jobs.pop(i)
            save_jobs(jobs)
            return removed
    return None