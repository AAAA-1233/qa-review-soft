from __future__ import annotations

import mimetypes
import posixpath
import zipfile
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from app import models
from app.database import DATA_DIR

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
UPLOAD_DIR = DATA_DIR / "uploads"


def safe_upload_name(name: str | None, fallback: str) -> Path:
    raw = (name or fallback).replace("\\", "/")
    parts = [part for part in raw.split("/") if part and part not in {".", ".."}]
    return Path(*parts) if parts else Path(fallback)


async def save_upload(file: UploadFile, target_dir: Path, fallback: str) -> Path:
    relative = safe_upload_name(file.filename, fallback)
    target = target_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as handle:
        while chunk := await file.read(1024 * 1024):
            handle.write(chunk)
    return target


def upload_project_dir(project_id: str) -> Path:
    path = UPLOAD_DIR / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def media_response(project: models.Project, media_ref: str) -> Response:
    if not project.media_path:
        raise HTTPException(404, "Project has no media resource")
    media_path = Path(project.media_path)
    if media_path.is_file() and media_path.suffix.lower() == ".zip":
        return _zip_media_response(media_path, media_ref)
    if media_path.is_file():
        return FileResponse(media_path, media_type=_mime_type(media_path.name))
    if media_path.is_dir():
        file_path = _find_in_directory(media_path, media_ref)
        if file_path:
            return FileResponse(file_path, media_type=_mime_type(file_path.name))
    raise HTTPException(404, "Media file not found")


def _zip_media_response(zip_path: Path, media_ref: str) -> Response:
    with zipfile.ZipFile(zip_path) as archive:
        entry = _find_in_zip(archive, media_ref)
        if not entry:
            raise HTTPException(404, "Media file not found in zip")
        data = archive.read(entry)
    return Response(content=data, media_type=_mime_type(entry))


def _find_in_zip(archive: zipfile.ZipFile, media_ref: str) -> str | None:
    target = _normalize_ref(media_ref)
    target_name = posixpath.basename(target)
    entries = [item.filename for item in archive.infolist() if not item.is_dir()]
    by_normalized = {_normalize_ref(entry): entry for entry in entries}
    if target in by_normalized:
        return by_normalized[target]
    for normalized, entry in by_normalized.items():
        if normalized.endswith("/" + target) or posixpath.basename(normalized) == target_name:
            return entry
    return None


def _find_in_directory(root: Path, media_ref: str) -> Path | None:
    target = Path(_normalize_ref(media_ref))
    direct = root / target
    if _is_inside(root, direct) and direct.is_file():
        return direct
    target_name = target.name
    for file_path in root.rglob("*"):
        if file_path.is_file() and file_path.name == target_name:
            return file_path
    return None


def _normalize_ref(media_ref: str) -> str:
    cleaned = media_ref.replace("\\", "/")
    if cleaned.startswith("zip://"):
        cleaned = cleaned.removeprefix("zip://")
    cleaned = cleaned.split("?", 1)[0].split("#", 1)[0]
    return posixpath.normpath(cleaned).lstrip("/")


def _is_inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _mime_type(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"
