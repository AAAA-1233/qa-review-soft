from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from app.schemas import ProviderPreset


PROVIDER_PRESETS = [
    ProviderPreset(id="openai", name="OpenAI", protocol="openai-compatible", base_url="https://api.openai.com/v1", default_model="", key_hint="OPENAI_API_KEY"),
    ProviderPreset(id="azure-openai", name="Azure OpenAI", protocol="openai-compatible", base_url="https://{resource}.openai.azure.com/openai/v1", default_model="", key_hint="AZURE_OPENAI_API_KEY"),
    ProviderPreset(id="anthropic", name="Anthropic Claude", protocol="anthropic-messages", base_url="https://api.anthropic.com", default_model="", key_hint="ANTHROPIC_API_KEY"),
    ProviderPreset(id="gemini", name="Google Gemini", protocol="gemini-generate-content", base_url="https://generativelanguage.googleapis.com/v1beta", default_model="", key_hint="GEMINI_API_KEY"),
    ProviderPreset(id="deepseek", name="DeepSeek", protocol="openai-compatible", base_url="https://api.deepseek.com", default_model="", key_hint="DEEPSEEK_API_KEY"),
    ProviderPreset(id="kimi", name="Kimi / Moonshot", protocol="openai-compatible", base_url="https://api.moonshot.ai/v1", default_model="", key_hint="MOONSHOT_API_KEY"),
    ProviderPreset(id="dashscope", name="阿里云百炼 / DashScope", protocol="openai-compatible", base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", default_model="", key_hint="DASHSCOPE_API_KEY"),
    ProviderPreset(id="siliconflow", name="硅基流动 / SiliconFlow", protocol="openai-compatible", base_url="https://api.siliconflow.cn/v1", default_model="", key_hint="SILICONFLOW_API_KEY"),
    ProviderPreset(id="zhipu", name="智谱 GLM", protocol="openai-compatible", base_url="https://open.bigmodel.cn/api/paas/v4", default_model="", key_hint="ZHIPU_API_KEY"),
    ProviderPreset(id="hunyuan", name="腾讯混元", protocol="openai-compatible", base_url="https://api.hunyuan.cloud.tencent.com/v1", default_model="", key_hint="HUNYUAN_API_KEY"),
    ProviderPreset(id="openrouter", name="OpenRouter", protocol="openai-compatible", base_url="https://openrouter.ai/api/v1", default_model="", key_hint="OPENROUTER_API_KEY"),
    ProviderPreset(id="ollama", name="Ollama 本地", protocol="openai-compatible", base_url="http://127.0.0.1:11434/v1", default_model="", key_hint="optional"),
    ProviderPreset(id="custom", name="自定义", protocol="openai-compatible", base_url="", default_model="", key_hint="API_KEY"),
]


@dataclass
class ReviewResult:
    status: str
    score: float
    reason: str
    raw: str


class AIProviderError(RuntimeError):
    pass


def _client_options(config) -> dict:
    options = {"timeout": config.timeout}
    proxy_url = (getattr(config, "proxy_url", "") or "").strip()
    if proxy_url:
        options["proxy"] = proxy_url
    return options


def render_prompt(template: str, sample: dict) -> str:
    value = template
    for key, replacement in sample.items():
        value = value.replace("{{" + key + "}}", str(replacement or ""))
    return value


async def review_sample(config, prompt: str, sample: dict) -> ReviewResult:
    text = render_prompt(prompt, sample)
    if not config.api_key and not config.base_url.startswith("http://127.0.0.1"):
        score = 88 if sample.get("answer") else 20
        status = "PASS" if score >= 70 else "FAIL"
        raw = {"offline": True, "status": status, "score": score, "reason": "未配置 API Key，使用本地规则检查。"}
        return ReviewResult(status=status, score=score, reason=raw["reason"], raw=json.dumps(raw, ensure_ascii=False))
    try:
        if config.protocol == "anthropic-messages":
            return await _anthropic(config, text)
        if config.protocol == "gemini-generate-content":
            return await _gemini(config, text)
        return await _openai_compatible(config, text)
    except httpx.ConnectError as exc:
        raise AIProviderError(f"无法连接模型服务：{config.base_url}。请检查网络、代理、防火墙或 Base URL。原始错误：{exc}") from exc
    except httpx.TimeoutException as exc:
        raise AIProviderError(f"模型服务请求超时：{config.base_url}。请检查网络或调大 Timeout。原始错误：{exc}") from exc
    except httpx.RequestError as exc:
        raise AIProviderError(f"模型服务请求失败：{config.base_url}。请检查网络、代理或服务商状态。原始错误：{exc}") from exc


async def chat_test(config, prompt: str) -> str:
    if not config.base_url:
        raise AIProviderError("Base URL 不能为空。")
    if not config.model:
        raise AIProviderError("模型名称不能为空。")
    if not config.api_key and not config.base_url.startswith(("http://127.0.0.1", "http://localhost")):
        raise AIProviderError("API Key 不能为空。")
    try:
        if config.protocol == "anthropic-messages":
            return await _anthropic_chat(config, prompt)
        if config.protocol == "gemini-generate-content":
            return await _gemini_chat(config, prompt)
        return await _openai_compatible_chat(config, prompt)
    except httpx.ConnectError as exc:
        raise AIProviderError(f"无法连接模型服务：{config.base_url}。请检查网络、代理、防火墙或 Base URL。原始错误：{exc}") from exc
    except httpx.TimeoutException as exc:
        raise AIProviderError(f"模型服务请求超时：{config.base_url}。请检查网络或调大 Timeout。原始错误：{exc}") from exc
    except httpx.RequestError as exc:
        raise AIProviderError(f"模型服务请求失败：{config.base_url}。请检查网络、代理或服务商状态。原始错误：{exc}") from exc


async def _openai_compatible(config, text: str) -> ReviewResult:
    payload = {
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "messages": [
            {"role": "system", "content": "你是问答数据集质量审核器。只输出 JSON，字段为 pass, score, reason。"},
            {"role": "user", "content": text},
        ],
    }
    async with httpx.AsyncClient(**_client_options(config)) as client:
        response = await client.post(
            config.base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
            json=payload,
        )
    if response.status_code >= 400:
        raise AIProviderError(response.text[:800])
    raw = response.text
    content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    return _parse_model_json(content, raw)


async def _openai_compatible_chat(config, prompt: str) -> str:
    payload = {
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": min(config.max_tokens or 512, 1024),
        "messages": [
            {"role": "system", "content": "你是模型连接测试助手。请直接回答用户问题。"},
            {"role": "user", "content": prompt},
        ],
    }
    async with httpx.AsyncClient(**_client_options(config)) as client:
        response = await client.post(
            config.base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
            json=payload,
        )
    if response.status_code >= 400:
        raise AIProviderError(response.text[:1200])
    return response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()


async def _anthropic(config, text: str) -> ReviewResult:
    payload = {"model": config.model, "max_tokens": config.max_tokens, "messages": [{"role": "user", "content": text}]}
    async with httpx.AsyncClient(**_client_options(config)) as client:
        response = await client.post(
            config.base_url.rstrip("/") + "/v1/messages",
            headers={"x-api-key": config.api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            json=payload,
        )
    if response.status_code >= 400:
        raise AIProviderError(response.text[:800])
    raw = response.text
    blocks = response.json().get("content", [])
    content = "\n".join(block.get("text", "") for block in blocks if block.get("type") == "text")
    return _parse_model_json(content, raw)


async def _anthropic_chat(config, prompt: str) -> str:
    payload = {"model": config.model, "max_tokens": min(config.max_tokens or 512, 1024), "messages": [{"role": "user", "content": prompt}]}
    async with httpx.AsyncClient(**_client_options(config)) as client:
        response = await client.post(
            config.base_url.rstrip("/") + "/v1/messages",
            headers={"x-api-key": config.api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            json=payload,
        )
    if response.status_code >= 400:
        raise AIProviderError(response.text[:1200])
    blocks = response.json().get("content", [])
    return "\n".join(block.get("text", "") for block in blocks if block.get("type") == "text").strip()


async def _gemini(config, text: str) -> ReviewResult:
    url = f"{config.base_url.rstrip('/')}/models/{config.model}:generateContent"
    async with httpx.AsyncClient(**_client_options(config)) as client:
        response = await client.post(
            url,
            headers={"x-goog-api-key": config.api_key, "Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": text}]}]},
        )
    if response.status_code >= 400:
        raise AIProviderError(response.text[:800])
    raw = response.text
    candidates = response.json().get("candidates", [])
    content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "") if candidates else ""
    return _parse_model_json(content, raw)


async def _gemini_chat(config, prompt: str) -> str:
    url = f"{config.base_url.rstrip('/')}/models/{config.model}:generateContent"
    async with httpx.AsyncClient(**_client_options(config)) as client:
        response = await client.post(
            url,
            headers={"x-goog-api-key": config.api_key, "Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
        )
    if response.status_code >= 400:
        raise AIProviderError(response.text[:1200])
    candidates = response.json().get("candidates", [])
    return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip() if candidates else ""


def _parse_model_json(content: str, raw: str) -> ReviewResult:
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        data = json.loads(content[start:end] if start >= 0 and end > start else content)
        passed = _parse_pass_value(data.get("pass", data.get("passed", False)))
        score = float(data.get("score", 100 if passed else 0))
        reason = str(data.get("reason", ""))
        return ReviewResult(status="PASS" if passed else "FAIL", score=score, reason=reason, raw=raw)
    except Exception:
        return ReviewResult(status="FAIL", score=0, reason="模型未返回可解析 JSON。", raw=raw)


def _parse_pass_value(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "pass", "passed", "yes", "保留", "通过", "合格"}:
            return True
        if normalized in {"false", "fail", "failed", "no", "删除", "不通过", "不合格"}:
            return False
    return False
