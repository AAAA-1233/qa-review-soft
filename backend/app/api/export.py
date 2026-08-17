from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.services.auth import get_current_user, require_project
from app.services.exporter import export_project

router = APIRouter(prefix="/projects/{project_id}/export", tags=["export"])


@router.post("")
def export(project_id: str, mode: str = "merged_pass", only_pass: bool | None = None, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    require_project(db, project_id, user)
    try:
        if only_pass is not None and mode == "merged_pass":
            mode = "human_pass" if only_pass else "merged_pass"
        return export_project(db, project_id, mode=mode)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/download")
def download_export(project_id: str, mode: str = "merged_pass", db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    require_project(db, project_id, user)
    try:
        result = export_project(db, project_id, mode=mode)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    path = Path(result["path"])
    return FileResponse(path, media_type="application/x-ndjson; charset=utf-8", filename=result["filename"])
