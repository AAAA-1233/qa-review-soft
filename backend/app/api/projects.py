from datetime import datetime
from types import SimpleNamespace

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.config import ALLOW_SERVER_PATH_IMPORT
from app.database import get_db
from app.schemas import InspectResult, ProjectCreate, ProjectOut
from app.services.dataset import create_project_from_path, inspect_dataset
from app.services.media import media_response, save_upload, upload_project_dir

router = APIRouter(prefix="/projects", tags=["projects"])


def project_out(db: Session, project: models.Project) -> ProjectOut:
    reviewed = db.scalar(select(func.count(models.Sample.id)).where(models.Sample.project_id == project.id, models.Sample.review_status != "UNREVIEWED")) or 0
    ai_reviewed = db.scalar(select(func.count(models.Sample.id)).where(models.Sample.project_id == project.id, models.Sample.ai_status != "PENDING")) or 0
    total = db.scalar(select(func.count(models.Sample.id)).where(models.Sample.project_id == project.id)) or project.total
    return ProjectOut(
        id=project.id,
        name=project.name,
        type=project.dataset_type,
        total=total,
        reviewed=reviewed,
        ai_reviewed=ai_reviewed,
        path=project.project_path,
        source_path=project.source_path,
        media_path=project.media_path,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return [project_out(db, project) for project in db.scalars(select(models.Project).order_by(models.Project.updated_at.desc()))]


@router.post("", response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    if not ALLOW_SERVER_PATH_IMPORT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "服务器模式已关闭路径导入，请上传数据文件创建项目")
    try:
        project = create_project_from_path(db, payload)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return project_out(db, project)


@router.post("/upload", response_model=ProjectOut)
async def create_project_upload(
    name: str = Form(...),
    dataset_type: str = Form(""),
    project_path: str = Form(""),
    dataset_file: UploadFile = File(...),
    media_files: list[UploadFile] | None = File(None),
    db: Session = Depends(get_db),
):
    upload_root = upload_project_dir(str(datetime.utcnow().timestamp()).replace(".", ""))
    source_path = await save_upload(dataset_file, upload_root / "source", "dataset.json")
    media_path = ""
    saved_media: list[str] = []
    if dataset_type == "图片问答":
        for index, media_file in enumerate(media_files or []):
            if not media_file.filename:
                continue
            saved_media.append(str(await save_upload(media_file, upload_root / "media", f"media-{index}")))
    if len(saved_media) == 1:
        media_path = saved_media[0]
    elif saved_media:
        media_path = str(upload_root / "media")
    payload = SimpleNamespace(
        name=name,
        dataset_type=dataset_type,
        source_path=str(source_path),
        project_path=project_path or str(upload_root),
        media_path=media_path or None,
    )
    try:
        project = create_project_from_path(db, payload)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return project_out(db, project)


@router.post("/inspect-upload", response_model=InspectResult)
async def inspect_upload(dataset_file: UploadFile = File(...)):
    upload_root = upload_project_dir("inspect")
    source_path = await save_upload(dataset_file, upload_root, "dataset.json")
    try:
        return inspect_dataset(str(source_path))
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    return project_out(db, project)


@router.get("/{project_id}/media")
def get_media(project_id: str, path: str = Query(...), db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return media_response(project, path)


@router.patch("/{project_id}", response_model=ProjectOut)
def rename_project(project_id: str, name: str, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    project.name = name
    project.updated_at = datetime.utcnow()
    db.commit()
    return project_out(db, project)


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    db.delete(project)
    db.commit()
    return {"ok": True}


@router.post("/inspect", response_model=InspectResult)
def inspect(path: str):
    if not ALLOW_SERVER_PATH_IMPORT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "服务器模式已关闭路径识别，请上传数据文件识别字段")
    try:
        return inspect_dataset(path)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
