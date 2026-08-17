from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ReviewStatus = Literal["PASS", "FAIL", "SKIP", "UNREVIEWED"]


class ProjectOut(BaseModel):
    id: str
    name: str
    type: str
    total: int
    reviewed: int
    ai_reviewed: int
    path: str
    source_path: str
    media_path: str | None = None
    created_at: datetime
    updated_at: datetime


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    dataset_type: str = "图片问答"
    source_path: str = "local://sample.json"
    project_path: str = "projects/default"
    media_path: str | None = None


class SampleOut(BaseModel):
    id: int
    external_id: str
    question: str
    answer: str
    media: list[str]
    tags: list[str]
    review: str
    ai: str
    ai_score: float
    ai_reason: str | None = None
    note: str | None = None
    edited_question: str | None = None
    edited_answer: str | None = None
    conversation: list[dict[str, str]] = []


class SamplePage(BaseModel):
    items: list[SampleOut]
    total: int
    limit: int
    offset: int


class ReviewIn(BaseModel):
    status: ReviewStatus
    note: str | None = None
    edited_question: str | None = None
    edited_answer: str | None = None


class PromptIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1)


class PromptOut(PromptIn):
    id: int
    project_id: str


class ProviderPreset(BaseModel):
    id: str
    name: str
    protocol: str
    base_url: str
    default_model: str
    key_hint: str


class AIConfigIn(BaseModel):
    provider_id: str = "custom"
    name: str = "默认配置"
    protocol: str = "openai-compatible"
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-5-mini"
    api_key: str = ""
    proxy_url: str = ""
    temperature: float = 0.1
    max_tokens: int = 1200
    timeout: int = 60


class AIConfigOut(AIConfigIn):
    id: int
    project_id: str
    api_key: str


class AIChatTestIn(AIConfigIn):
    prompt: str = "请回复：模型连接测试成功。"


class AIChatTestOut(BaseModel):
    ok: bool
    content: str
    elapsed_ms: int
    protocol: str
    model: str


class AITaskIn(BaseModel):
    config_id: int
    prompt_id: int
    range_filter: str = "UNREVIEWED"


class AITaskOut(BaseModel):
    id: int
    project_id: str
    config_id: int
    prompt_id: int
    status: str
    range_filter: str
    total: int
    completed: int
    failed: int
    error: str | None = None
    updated_at: datetime


class AITaskResultOut(BaseModel):
    sample_id: int
    external_id: str
    question: str
    ai_status: str
    ai_score: float
    ai_reason: str | None = None
    review_status: str
    updated_at: datetime


class InspectResult(BaseModel):
    dataset_type: str
    total: int
    field_map: dict[str, str]
    confidence: dict[str, float]
    preview: list[dict[str, Any]]


class StatsOut(BaseModel):
    review: dict[str, int]
    ai: dict[str, int]
    agreement: float
    total: int
