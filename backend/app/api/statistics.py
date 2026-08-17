from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.schemas import StatsOut
from app.services.statistics import agreement, ai_counts, review_counts

router = APIRouter(prefix="/projects/{project_id}/statistics", tags=["statistics"])


@router.get("", response_model=StatsOut)
def stats(project_id: str, db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(models.Sample.id)).where(models.Sample.project_id == project_id)) or 0
    return StatsOut(review=review_counts(db, project_id), ai=ai_counts(db, project_id), agreement=agreement(db, project_id), total=total)
