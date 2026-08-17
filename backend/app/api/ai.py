from datetime import datetime
import socket
from time import perf_counter

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.schemas import AIChatTestIn, AIChatTestOut, AIConfigIn, AIConfigOut, AITaskIn, AITaskOut, AITaskResultOut, ProviderPreset
from app.services.providers import AIProviderError, PROVIDER_PRESETS, chat_test
from app.services.tasks import refresh_ai_task_queue, run_ai_task, task_to_dict

router = APIRouter(prefix="/projects/{project_id}/ai", tags=["ai"])
provider_router = APIRouter(prefix="/providers", tags=["providers"])


@provider_router.get("", response_model=list[ProviderPreset])
def providers():
    return PROVIDER_PRESETS


@provider_router.get("/local-proxy")
def local_proxy():
    for port in (7897, 7890, 10809, 10808, 10807, 1080, 20170, 2080, 8080):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.15):
                return {"proxy_url": f"http://127.0.0.1:{port}"}
        except OSError:
            continue
    return {"proxy_url": ""}


@router.get("/configs", response_model=list[AIConfigOut])
def configs(project_id: str, db: Session = Depends(get_db)):
    query = select(models.AIConfig).where(models.AIConfig.project_id == project_id).order_by(models.AIConfig.id.desc())
    return [_config_out(item) for item in db.scalars(query)]


@router.post("/configs", response_model=AIConfigOut)
def save_config(project_id: str, payload: AIConfigIn, db: Session = Depends(get_db)):
    data = payload.model_dump()
    config = db.scalars(
        select(models.AIConfig).where(models.AIConfig.project_id == project_id).order_by(models.AIConfig.id.desc())
    ).first()
    if config:
        if data.get("api_key") == "******":
            data["api_key"] = config.api_key
        for key, value in data.items():
            setattr(config, key, value)
    else:
        config = models.AIConfig(project_id=project_id, **data)
        db.add(config)
    db.commit()
    db.refresh(config)
    return _config_out(config)


@router.post("/test")
async def test_config(payload: AIConfigIn):
    if not payload.base_url:
        raise HTTPException(400, "Base URL 不能为空")
    return {"ok": True, "protocol": payload.protocol, "base_url": payload.base_url, "model": payload.model}


@router.post("/chat-test", response_model=AIChatTestOut)
async def chat_test_config(payload: AIChatTestIn):
    started = perf_counter()
    try:
        content = await chat_test(payload, payload.prompt)
    except AIProviderError as exc:
        raise HTTPException(502, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"模型请求失败：{exc}") from exc
    return AIChatTestOut(
        ok=True,
        content=content,
        elapsed_ms=round((perf_counter() - started) * 1000),
        protocol=payload.protocol,
        model=payload.model,
    )


@router.post("/tasks", response_model=AITaskOut)
def start_task(project_id: str, payload: AITaskIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    config = db.get(models.AIConfig, payload.config_id)
    prompt = db.get(models.PromptTemplate, payload.prompt_id)
    if not config or config.project_id != project_id:
        raise HTTPException(400, "AI 配置不存在")
    if not prompt or prompt.project_id != project_id:
        raise HTTPException(400, "Prompt 不存在")
    task = models.AITask(project_id=project_id, config_id=payload.config_id, prompt_id=payload.prompt_id, range_filter=payload.range_filter, status="queued")
    db.add(task)
    db.commit()
    db.refresh(task)
    background.add_task(run_ai_task, task.id)
    return AITaskOut(**task_to_dict(task))


@router.get("/tasks", response_model=list[AITaskOut])
def list_tasks(project_id: str, db: Session = Depends(get_db)):
    return [AITaskOut(**task_to_dict(task)) for task in db.scalars(select(models.AITask).where(models.AITask.project_id == project_id).order_by(models.AITask.id.desc()))]


@router.get("/tasks/{task_id}/results", response_model=list[AITaskResultOut])
def task_results(project_id: str, task_id: int, limit: int = 80, db: Session = Depends(get_db)):
    task = db.get(models.AITask, task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(404, "任务不存在")
    safe_limit = max(1, min(limit, 200))
    query = (
        select(models.Sample)
        .where(models.Sample.project_id == project_id, models.Sample.ai_status != "PENDING")
        .order_by(models.Sample.updated_at.desc(), models.Sample.id.desc())
        .limit(safe_limit)
    )
    return [
        AITaskResultOut(
            sample_id=sample.id,
            external_id=sample.external_id,
            question=sample.question,
            ai_status=sample.ai_status,
            ai_score=sample.ai_score,
            ai_reason=sample.ai_reason,
            review_status=sample.review_status,
            updated_at=sample.updated_at,
        )
        for sample in db.scalars(query)
    ]


@router.post("/tasks/{task_id}/{action}", response_model=AITaskOut)
def task_action(project_id: str, task_id: int, action: str, background: BackgroundTasks, db: Session = Depends(get_db)):
    task = db.get(models.AITask, task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(404, "任务不存在")
    if action not in {"pause", "resume", "stop", "refresh"}:
        raise HTTPException(400, "动作不支持")
    if action == "refresh":
        refresh_ai_task_queue(db, task)
        db.commit()
        return AITaskOut(**task_to_dict(task))
    task.status = {"pause": "paused", "resume": "queued", "stop": "stopped"}[action]
    if action == "resume":
        refresh_ai_task_queue(db, task)
    task.updated_at = datetime.utcnow()
    db.commit()
    if action == "resume":
        background.add_task(run_ai_task, task.id)
    return AITaskOut(**task_to_dict(task))


def _config_out(config: models.AIConfig) -> AIConfigOut:
    return AIConfigOut(
        id=config.id,
        project_id=config.project_id,
        provider_id=config.provider_id,
        name=config.name,
        protocol=config.protocol,
        base_url=config.base_url,
        model=config.model,
        api_key="******" if config.api_key else "",
        proxy_url=config.proxy_url or "",
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        timeout=config.timeout,
    )
