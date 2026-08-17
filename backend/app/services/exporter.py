import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.database import DATA_DIR
from app.services.review_logic import is_human_pass


EXPORT_MODES = {
    "human_pass": "人工通过",
    "ai_pass": "AI保留",
    "merged_pass": "人工优先合并",
}


def export_project(db: Session, project_id: str, mode: str = "merged_pass") -> dict:
    project = db.get(models.Project, project_id)
    if not project:
        raise ValueError("project not found")
    if mode not in EXPORT_MODES:
        raise ValueError("unsupported export mode")
    rows = [_export_row(sample, mode) for sample in db.scalars(select(models.Sample).where(models.Sample.project_id == project_id).order_by(models.Sample.id))]
    rows = [row for row in rows if row is not None]
    out_dir = Path(project.project_path) / "exports"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        out_dir = DATA_DIR / "exports" / project_id
        out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{mode}.jsonl"
    with out_file.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    metadata = out_dir / "review_metadata.json"
    metadata.write_text(json.dumps({"project": project.name, "rows": len(rows), "mode": mode, "mode_label": EXPORT_MODES[mode]}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(out_file), "metadata": str(metadata), "rows": len(rows), "mode": mode, "mode_label": EXPORT_MODES[mode], "filename": out_file.name}


def _export_row(sample: models.Sample, mode: str) -> dict | None:
    decision = _decision_for(sample, mode)
    if decision is None:
        return None
    try:
        raw = json.loads(sample.raw_json)
    except json.JSONDecodeError:
        raw = {"raw": sample.raw_json}
    row = dict(raw) if isinstance(raw, dict) else {"raw": raw}
    row["_audit"] = {
        "sample_id": sample.id,
        "external_id": sample.external_id,
        "export_mode": mode,
        "final_decision": decision["decision"],
        "final_source": decision["source"],
        "human_status": sample.review_status,
        "ai_status": sample.ai_status,
        "ai_score": sample.ai_score,
        "ai_reason": sample.ai_reason,
        "note": sample.note,
        "edited_question": sample.edited_question,
        "edited_answer": sample.edited_answer,
    }
    return row


def _decision_for(sample: models.Sample, mode: str) -> dict | None:
    if mode == "human_pass":
        return {"decision": "PASS", "source": "human"} if is_human_pass(sample.review_status) else None
    if mode == "ai_pass":
        return {"decision": "PASS", "source": "ai"} if sample.ai_status == "PASS" else None
    if is_human_pass(sample.review_status):
        return {"decision": "PASS", "source": "human"}
    if sample.review_status == "FAIL":
        return None
    if sample.ai_status == "PASS":
        return {"decision": "PASS", "source": "ai"}
    return None
