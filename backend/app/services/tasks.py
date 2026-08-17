from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.database import SessionLocal
from app.services.providers import AIProviderError, review_sample


def ai_sample_query(project_id: str, range_filter: str):
    query = select(models.Sample).where(models.Sample.project_id == project_id)
    if range_filter in {"UNREVIEWED", "HUMAN_UNREVIEWED", "HUMAN_UNREVIEWED_AI_PENDING"}:
        return query.where(models.Sample.review_status == "UNREVIEWED", models.Sample.ai_status == "PENDING")
    if range_filter == "AI_PENDING":
        return query.where(models.Sample.ai_status == "PENDING")
    return query


def refresh_ai_task_queue(db: Session, task: models.AITask) -> models.AITask:
    remaining = list(db.scalars(ai_sample_query(task.project_id, task.range_filter)))
    task.total = len(remaining)
    task.completed = 0
    task.failed = 0
    task.error = None
    task.updated_at = datetime.utcnow()
    return task


async def run_ai_task(task_id: int) -> None:
    db = SessionLocal()
    try:
      task = db.get(models.AITask, task_id)
      if not task:
          return
      config = db.get(models.AIConfig, task.config_id)
      prompt = db.get(models.PromptTemplate, task.prompt_id)
      if not config or not prompt:
          task.status = "failed"
          task.error = "AI 配置或 Prompt 不存在"
          db.commit()
          return
      task.status = "running"
      task.updated_at = datetime.utcnow()
      db.commit()
      samples = list(db.scalars(ai_sample_query(task.project_id, task.range_filter)))
      task.total = len(samples)
      task.completed = 0
      task.failed = 0
      task.error = None
      db.commit()
      for sample in samples:
          task = db.get(models.AITask, task_id)
          if not task or task.status in {"paused", "stopped"}:
              return
          try:
              result = await review_sample(
                  config,
                  prompt.content,
                  {
                      "question": sample.question,
                      "answer": sample.answer,
                      "conversation": sample.conversation_json or "",
                      "image": sample.media_json or "",
                      "metadata": sample.metadata_json or "",
                  },
              )
              sample.ai_status = result.status
              sample.ai_score = result.score
              sample.ai_reason = result.reason
              sample.ai_raw_response = result.raw
              sample.updated_at = datetime.utcnow()
              task.completed += 1
          except AIProviderError as exc:
              sample.ai_status = "FAIL"
              sample.ai_reason = str(exc)
              sample.updated_at = datetime.utcnow()
              task.failed += 1
          except Exception as exc:
              sample.ai_status = "FAIL"
              sample.ai_reason = f"AI 审核异常：{exc}"
              sample.updated_at = datetime.utcnow()
              task.failed += 1
              task.error = str(exc)
          task.updated_at = datetime.utcnow()
          db.commit()
      task.status = "completed"
      task.updated_at = datetime.utcnow()
      db.commit()
    finally:
      db.close()


def task_to_dict(task: models.AITask) -> dict:
    return {
        "id": task.id,
        "project_id": task.project_id,
        "config_id": task.config_id,
        "prompt_id": task.prompt_id,
        "status": task.status,
        "range_filter": task.range_filter,
        "total": task.total,
        "completed": task.completed,
        "failed": task.failed,
        "error": task.error,
        "updated_at": task.updated_at,
    }
