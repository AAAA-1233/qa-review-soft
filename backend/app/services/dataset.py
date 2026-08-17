from __future__ import annotations

import csv
import json
import uuid
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models

QUESTION_KEYS = ["question", "query", "prompt", "instruction", "input", "user", "human", "title", "问题", "题目", "提问", "用户"]
ANSWER_KEYS = ["answer", "response", "output", "completion", "assistant", "gpt", "bot", "reply", "答案", "回复", "回答"]
IMAGE_KEYS = ["image", "image_path", "images", "img", "picture", "photo", "media", "url", "图片", "图像", "照片"]
CONVERSATION_KEYS = ["conversation", "conversations", "messages", "dialogue", "dialogs", "history", "turns", "chat", "对话", "会话", "聊天记录"]


def seed_database(db: Session) -> None:
    if db.scalar(select(func.count(models.Project.id))):
        return
    project = models.Project(
        id="geovqa",
        name="GeoVQA 审核",
        dataset_type="图片问答",
        source_path="E:/datasets/geovqa/train.json",
        project_path="D:/qa-projects/GeoVQA",
        media_path="E:/datasets/geovqa/images.zip",
        total=4,
    )
    db.add(project)
    rows = [
        ("S-000184", "图中河流主要流经哪一种地形区？", "该河流主要流经山地和丘陵交错区，河谷较窄，坡度较大。", ["zip://images/geo/river_valley_0184.jpg"], "UNREVIEWED", "FAIL", 62),
        ("S-000185", "如果当地降水集中在夏季，最容易出现的灾害是什么？", "容易出现山洪、滑坡和泥石流等地质灾害。", ["zip://images/geo/mountain_0185.jpg"], "PASS", "PASS", 91),
        ("S-000186", "请判断这张图片是否适合作为城市交通拥堵问题的配图。", "不适合。图片主体是乡村道路，并未体现城市道路车流密集或拥堵状态。", ["zip://images/traffic/rural_0186.jpg"], "UNREVIEWED", "FAIL", 48),
        ("S-000187", "多轮对话中，用户第二轮追问是否依赖第一轮问题？", "依赖。第二轮的“它”指代第一轮中提到的湖泊，需要结合上下文才能理解。", [], "SKIP", "PENDING", 0),
    ]
    for external_id, question, answer, media, review, ai, score in rows:
        db.add(
            models.Sample(
                project_id=project.id,
                external_id=external_id,
                question=question,
                answer=answer,
                media_json=json.dumps(media, ensure_ascii=False),
                metadata_json=json.dumps({"tags": ["待复核"] if review == "UNREVIEWED" else []}, ensure_ascii=False),
                raw_json=json.dumps({"id": external_id, "question": question, "answer": answer, "image": media}, ensure_ascii=False),
                review_status=review,
                ai_status=ai,
                ai_score=score,
            )
        )
    db.add(
        models.PromptTemplate(
            project_id=project.id,
            name="问答事实一致性",
            content="问题：{{question}}\n答案：{{answer}}\n图片：{{image}}\n请输出 JSON：pass, score, reason。",
        )
    )
    db.commit()


def inspect_dataset(path: str) -> dict[str, Any]:
    rows = load_rows(path, limit=80)
    field_map, confidence = infer_fields(rows)
    dataset_type = "多轮对话" if field_map.get("conversation") else "图片问答" if field_map.get("image") else "单轮问答"
    return {"dataset_type": dataset_type, "total": estimate_total(path), "field_map": field_map, "confidence": confidence, "preview": rows[:10]}


def load_rows(path: str, limit: int | None = None) -> list[dict[str, Any]]:
    if path.startswith("local://"):
        rows = _sample_rows()
        return rows[:limit] if limit else rows
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {path}")
    if file_path.suffix.lower() == ".jsonl":
        rows = []
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
                if limit and len(rows) >= limit:
                    break
        return rows
    if file_path.suffix.lower() == ".json":
        data = json.loads(file_path.read_text(encoding="utf-8"))
        rows = _rows_from_json(data)
        return rows[:limit] if limit else rows
    if file_path.suffix.lower() == ".csv":
        with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        return rows[:limit] if limit else rows
    raise ValueError(f"Unsupported dataset file type: {file_path.suffix or path}")


def create_project_from_path(db: Session, payload) -> models.Project:
    project_id = str(uuid.uuid4())[:8]
    rows = load_rows(payload.source_path)
    field_map, _confidence = infer_fields(rows)
    dataset_type = payload.dataset_type or ("多轮对话" if field_map.get("conversation") else "图片问答" if field_map.get("image") else "单轮问答")
    project = models.Project(
        id=project_id,
        name=payload.name,
        dataset_type=dataset_type,
        source_path=payload.source_path,
        project_path=payload.project_path,
        media_path=payload.media_path,
        total=len(rows),
    )
    db.add(project)
    for index, row in enumerate(rows):
        media = _media_from(row, field_map)
        question, answer = _qa_from_row(row, field_map)
        db.add(
            models.Sample(
                project_id=project_id,
                external_id=str(row.get("id", row.get("sample_id", f"S-{index + 1:06d}"))),
                question=question,
                answer=answer,
                conversation_json=json.dumps(row.get(field_map["conversation"]), ensure_ascii=False) if field_map.get("conversation") else None,
                media_json=json.dumps(media, ensure_ascii=False),
                metadata_json=json.dumps({"tags": []}, ensure_ascii=False),
                raw_json=json.dumps(row, ensure_ascii=False),
            )
        )
    if payload.media_path:
        build_zip_index(payload.media_path)
    db.commit()
    db.refresh(project)
    return project


def infer_fields(rows: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, float]]:
    keys = Counter(key for row in rows for key in row.keys())
    fields: dict[str, str] = {}
    confidence: dict[str, float] = {}
    for name, candidates in [("conversation", CONVERSATION_KEYS), ("question", QUESTION_KEYS), ("answer", ANSWER_KEYS), ("image", IMAGE_KEYS)]:
        best_key = ""
        best_score = 0.0
        for key, count in keys.most_common():
            values = [row.get(key) for row in rows[:80] if key in row]
            score = _field_score(name, key, values) + min(count / max(len(rows), 1), 1) * 0.35
            if score > best_score:
                best_key = key
                best_score = score
        if best_key and best_score >= 1.15:
            fields[name] = best_key
            confidence[name] = round(min(0.98, 0.52 + best_score / 5), 2)
    if fields.get("conversation"):
        fields.pop("question", None)
        fields.pop("answer", None)
        confidence.pop("question", None)
        confidence.pop("answer", None)
    return fields, confidence


def _field_score(field: str, key: str, values: list[Any]) -> float:
    normalized = _normalize_key(key)
    candidates = {
        "question": QUESTION_KEYS,
        "answer": ANSWER_KEYS,
        "image": IMAGE_KEYS,
        "conversation": CONVERSATION_KEYS,
    }[field]
    candidate_keys = [_normalize_key(candidate) for candidate in candidates]
    score = 0.0
    if normalized in candidate_keys:
        score += 3.0
    elif any(candidate and (candidate in normalized or normalized in candidate) for candidate in candidate_keys):
        score += 1.8
    if field == "image" and any(_looks_like_image(value) for value in values):
        score += 1.5
    if field == "conversation" and any(_looks_like_conversation(value) for value in values):
        score += 2.2
    if field in {"question", "answer"} and any(isinstance(value, str) and len(value.strip()) > 3 for value in values):
        score += 0.45
    return score


def _normalize_key(key: str) -> str:
    return "".join(char for char in str(key).lower() if char.isalnum() or "\u4e00" <= char <= "\u9fff")


def _looks_like_image(value: Any) -> bool:
    values = value if isinstance(value, list) else [value]
    for item in values:
        text = str(item).lower()
        if any(ext in text for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"]):
            return True
    return False


def _looks_like_conversation(value: Any) -> bool:
    if isinstance(value, list):
        if len(value) >= 2 and all(isinstance(item, dict) for item in value[:2]):
            keys = {_normalize_key(key) for item in value[:4] for key in item.keys()}
            return bool(keys & {"role", "from", "speaker", "author", "content", "value", "text"})
        return len(value) >= 2 and all(isinstance(item, str) for item in value[:2])
    if isinstance(value, dict):
        keys = {_normalize_key(key) for key in value.keys()}
        return bool(keys & {"messages", "conversation", "conversations", "history", "turns"})
    return False


def estimate_total(path: str) -> int:
    return len(load_rows(path))


def build_zip_index(path: str) -> dict[str, Any]:
    zip_path = Path(path)
    if not zip_path.exists():
        return {"path": path, "count": 0, "entries": []}
    with zipfile.ZipFile(zip_path) as archive:
        entries = [item.filename for item in archive.infolist() if not item.is_dir()]
    index_path = zip_path.with_suffix(zip_path.suffix + ".index.json")
    index_path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return {"path": path, "count": len(entries), "entries": entries[:50]}


def sample_to_dict(sample: models.Sample) -> dict[str, Any]:
    metadata = json.loads(sample.metadata_json or "{}")
    media = json.loads(sample.media_json or "[]")
    conversation = _normalize_conversation(json.loads(sample.conversation_json or "null"))
    return {
        "id": sample.id,
        "external_id": sample.external_id,
        "question": sample.question,
        "answer": sample.answer,
        "media": media,
        "tags": metadata.get("tags", []),
        "review": sample.review_status,
        "ai": sample.ai_status,
        "ai_score": sample.ai_score,
        "ai_reason": sample.ai_reason,
        "note": sample.note,
        "edited_question": sample.edited_question,
        "edited_answer": sample.edited_answer,
        "conversation": conversation,
    }


def _qa_from_row(row: dict[str, Any], field_map: dict[str, str]) -> tuple[str, str]:
    conversation = _value_for_field(row, field_map, "conversation")
    if conversation is not None:
        question = _conversation_text(conversation)
        answer = _last_assistant_message(conversation)
        return question, answer
    question = _string_value(_value_for_field(row, field_map, "question"))
    answer = _string_value(_value_for_field(row, field_map, "answer"))
    return question, answer


def _rows_from_json(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ["data", "samples", "items", "records", "rows", "examples", "dataset"]:
            value = data.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
        for value in data.values():
            if isinstance(value, list) and value and all(isinstance(item, dict) for item in value[:5]):
                return value
    return []


def _normalize_conversation(value: Any) -> list[dict[str, str]]:
    messages = value
    if isinstance(value, dict):
        for key in ["messages", "conversation", "conversations", "history", "turns", "dialogue"]:
            if key in value:
                messages = value[key]
                break
    if not isinstance(messages, list):
        return []
    turns = []
    for index, item in enumerate(messages):
        role, text = _message_parts(item)
        if not text:
            continue
        turns.append({"role": _display_role(role), "content": text, "index": str(index + 1)})
    return turns


def _display_role(role: str) -> str:
    normalized = str(role).lower()
    if normalized in {"用户", "user", "human"}:
        return "user"
    if normalized in {"助手", "assistant", "gpt", "bot", "model"}:
        return "assistant"
    if normalized in {"系统", "system"}:
        return "system"
    return normalized or "message"


def _conversation_text(value: Any) -> str:
    if isinstance(value, list):
        lines = []
        for item in value:
            role, text = _message_parts(item)
            if text:
                lines.append(f"{role}：{text}" if role else text)
        return "\n".join(lines)
    if isinstance(value, dict):
        for key in ["messages", "conversation", "conversations", "history", "turns", "dialogue"]:
            if key in value:
                return _conversation_text(value[key])
        return json.dumps(value, ensure_ascii=False)
    return _string_value(value)


def _last_assistant_message(value: Any) -> str:
    messages = value
    if isinstance(value, dict):
        for key in ["messages", "conversation", "conversations", "history", "turns", "dialogue"]:
            if key in value:
                messages = value[key]
                break
    if not isinstance(messages, list):
        return ""
    fallback = ""
    for item in messages:
        role, text = _message_parts(item)
        if text:
            fallback = text
        if role in {"助手", "assistant", "gpt", "bot"} and text:
            fallback = text
    return fallback


def _message_parts(item: Any) -> tuple[str, str]:
    if isinstance(item, str):
        return "", item.strip()
    if not isinstance(item, dict):
        return "", _string_value(item)
    raw_role = str(item.get("role", item.get("from", item.get("speaker", item.get("author", ""))))).lower()
    text = _string_value(item.get("content", item.get("value", item.get("text", item.get("message", "")))))
    if raw_role in {"user", "human", "用户"}:
        return "用户", text
    if raw_role in {"assistant", "gpt", "bot", "model", "助手"}:
        return "助手", text
    if raw_role in {"system", "系统"}:
        return "系统", text
    return raw_role, text


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return json.dumps(value, ensure_ascii=False)


def _media_from(row: dict[str, Any], field_map: dict[str, str]) -> list[str]:
    value = _value_for_field(row, field_map, "image")
    if not value:
        return []
    return value if isinstance(value, list) else [str(value)]


def _value_for_field(row: dict[str, Any], field_map: dict[str, str], field: str) -> Any:
    mapped = field_map.get(field)
    if mapped and mapped in row:
        return row.get(mapped)
    best_key = ""
    best_score = 0.0
    for key, value in row.items():
        score = _field_score(field, key, [value])
        if score > best_score:
            best_key = key
            best_score = score
    return row.get(best_key) if best_key and best_score >= 1.15 else None


def _sample_rows() -> list[dict[str, Any]]:
    return [
        {"id": "S-000184", "question": "图中河流主要流经哪一种地形区？", "answer": "该河流主要流经山地和丘陵交错区，河谷较窄，坡度较大。", "image": "images/geo/river_valley_0184.jpg"},
        {"id": "S-000185", "question": "如果当地降水集中在夏季，最容易出现的灾害是什么？", "answer": "容易出现山洪、滑坡和泥石流等地质灾害。", "image": "images/geo/mountain_0185.jpg"},
        {"id": "S-000186", "question": "请判断这张图片是否适合作为城市交通拥堵问题的配图。", "answer": "不适合。图片主体是乡村道路。", "image": "images/traffic/rural_0186.jpg"},
    ]
