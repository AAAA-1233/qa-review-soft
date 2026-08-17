from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.schemas import ReviewIn, SamplePage, SampleOut
from app.services.dataset import sample_to_dict
from app.services.review_logic import merged_status_condition

router = APIRouter(prefix="/projects/{project_id}/samples", tags=["samples"])


@router.get("", response_model=SamplePage)
def list_samples(
    project_id: str,
    status: str = "ALL",
    q: str = "",
    limit: int = Query(50, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(models.Sample).where(models.Sample.project_id == project_id)
    count_query = select(func.count(models.Sample.id)).where(models.Sample.project_id == project_id)
    condition = merged_status_condition(status)
    if condition is not None:
        query = query.where(condition)
        count_query = count_query.where(condition)
    elif status != "ALL":
        query = query.where(models.Sample.review_status == status)
        count_query = count_query.where(models.Sample.review_status == status)
    if q:
        condition = or_(models.Sample.external_id.contains(q), models.Sample.question.contains(q), models.Sample.answer.contains(q))
        query = query.where(condition)
        count_query = count_query.where(condition)
    items = [SampleOut(**sample_to_dict(sample)) for sample in db.scalars(query.order_by(models.Sample.id).limit(limit).offset(offset))]
    total = db.scalar(count_query) or 0
    return SamplePage(items=items, total=total, limit=limit, offset=offset)


@router.get("/{sample_id}", response_model=SampleOut)
def get_sample(project_id: str, sample_id: int, db: Session = Depends(get_db)):
    sample = db.get(models.Sample, sample_id)
    if not sample or sample.project_id != project_id:
        raise HTTPException(404, "样本不存在")
    return SampleOut(**sample_to_dict(sample))


@router.post("/{sample_id}/review", response_model=SampleOut)
def review_sample(project_id: str, sample_id: int, payload: ReviewIn, db: Session = Depends(get_db)):
    sample = db.get(models.Sample, sample_id)
    if not sample or sample.project_id != project_id:
        raise HTTPException(404, "样本不存在")
    previous = sample.review_status
    if previous != payload.status:
        db.add(models.ReviewHistory(project_id=project_id, sample_id=sample_id, previous_status=previous, next_status=payload.status, note=payload.note))
    sample.review_status = payload.status
    sample.note = payload.note
    sample.edited_question = payload.edited_question
    sample.edited_answer = payload.edited_answer
    sample.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(sample)
    return SampleOut(**sample_to_dict(sample))


@router.post("/undo")
def undo_review(project_id: str, db: Session = Depends(get_db)):
    history = db.scalar(select(models.ReviewHistory).where(models.ReviewHistory.project_id == project_id).order_by(models.ReviewHistory.id.desc()))
    if not history:
        return {"ok": False}
    sample = db.get(models.Sample, history.sample_id)
    if sample:
        sample.review_status = history.previous_status
    db.delete(history)
    db.commit()
    return {"ok": True}
