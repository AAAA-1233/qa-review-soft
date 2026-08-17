from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import models
from app.database import DATA_DIR


PROJECT_CHILD_TABLES = (
    models.ReviewHistory,
    models.PromptTemplate,
    models.AIConfig,
    models.AITask,
    models.Sample,
)


def delete_project_fully(db: Session, project: models.Project) -> dict:
    project_id = project.id
    file_paths = _owned_file_paths(project)
    deleted_rows: dict[str, int] = {}

    for table in PROJECT_CHILD_TABLES:
        result = db.execute(delete(table).where(table.project_id == project_id))
        deleted_rows[table.__tablename__] = int(result.rowcount or 0)

    db.delete(project)
    deleted_rows[models.Project.__tablename__] = 1
    db.commit()

    deleted_files = _delete_paths(file_paths)
    return {"rows": deleted_rows, "files": deleted_files}


def cleanup_orphan_project_rows(db: Session) -> dict[str, int]:
    project_ids = select(models.Project.id)
    deleted_rows: dict[str, int] = {}
    for table in PROJECT_CHILD_TABLES:
        result = db.execute(delete(table).where(table.project_id.not_in(project_ids)))
        deleted_rows[table.__tablename__] = int(result.rowcount or 0)
    db.commit()
    return deleted_rows


def _owned_file_paths(project: models.Project) -> list[Path]:
    candidates = [
        Path(project.project_path) if project.project_path else None,
        Path(project.source_path) if project.source_path else None,
        Path(project.media_path) if project.media_path else None,
        DATA_DIR / "exports" / project.id,
    ]
    owned = [_resolve(path) for path in candidates if path and _is_under_data_dir(path)]
    unique: list[Path] = []
    for path in sorted({item for item in owned}, key=lambda item: len(item.parts)):
        if not any(_is_same_or_child(path, parent) for parent in unique):
            unique.append(path)
    return unique


def _delete_paths(paths: list[Path]) -> list[str]:
    deleted: list[str] = []
    for path in paths:
        if not path.exists() or _resolve(path) == _resolve(DATA_DIR):
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        deleted.append(str(path))
    return deleted


def _is_under_data_dir(path: Path) -> bool:
    try:
        _resolve(path).relative_to(_resolve(DATA_DIR))
        return True
    except ValueError:
        return False


def _is_same_or_child(path: Path, parent: Path) -> bool:
    try:
        _resolve(path).relative_to(_resolve(parent))
        return True
    except ValueError:
        return False


def _resolve(path: Path) -> Path:
    return path.expanduser().resolve()
