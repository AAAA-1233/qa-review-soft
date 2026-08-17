from sqlalchemy import or_

from app import models

HUMAN_PASS_STATUSES = ("PASS", "SKIP")


def merged_status_condition(status: str):
    if status == "MERGED_PASS":
        return or_(
            models.Sample.review_status.in_(HUMAN_PASS_STATUSES),
            (models.Sample.review_status == "UNREVIEWED") & (models.Sample.ai_status == "PASS"),
        )
    if status == "MERGED_FAIL":
        return or_(
            models.Sample.review_status == "FAIL",
            (models.Sample.review_status == "UNREVIEWED") & (models.Sample.ai_status == "FAIL"),
        )
    if status == "MERGED_PENDING":
        return (models.Sample.review_status == "UNREVIEWED") & (models.Sample.ai_status == "PENDING")
    return None


def is_human_pass(status: str) -> bool:
    return status in HUMAN_PASS_STATUSES
