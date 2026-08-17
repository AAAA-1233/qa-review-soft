from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models


def review_counts(db: Session, project_id: str) -> dict[str, int]:
    rows = db.execute(
        select(models.Sample.review_status, func.count(models.Sample.id)).where(models.Sample.project_id == project_id).group_by(models.Sample.review_status)
    ).all()
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0, "UNREVIEWED": 0}
    counts.update({status: count for status, count in rows})
    return counts


def ai_counts(db: Session, project_id: str) -> dict[str, int]:
    rows = db.execute(
        select(models.Sample.ai_status, func.count(models.Sample.id)).where(models.Sample.project_id == project_id).group_by(models.Sample.ai_status)
    ).all()
    counts = {"PASS": 0, "FAIL": 0, "PENDING": 0}
    counts.update({status: count for status, count in rows})
    return counts


def agreement(db: Session, project_id: str) -> float:
    samples = db.scalars(select(models.Sample).where(models.Sample.project_id == project_id, models.Sample.review_status != "UNREVIEWED", models.Sample.ai_status != "PENDING")).all()
    if not samples:
        return 0
    matched = sum(1 for sample in samples if sample.review_status == sample.ai_status)
    return round(matched / len(samples) * 100, 1)
