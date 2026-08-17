from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import AUTH_SECRET, AUTH_TOKEN_EXPIRE_HOURS
from app.database import get_db

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_RE.match(normalized):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "邮箱格式不正确")
    return normalized


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(email: str, code: str) -> str:
    payload = f"{normalize_email(email)}:{code.strip()}".encode("utf-8")
    return hmac.new(AUTH_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def issue_token(user: models.User) -> str:
    expires_at = int((datetime.utcnow() + timedelta(hours=AUTH_TOKEN_EXPIRE_HOURS)).timestamp())
    payload = _b64(json.dumps({"sub": user.id, "email": user.email, "exp": expires_at}, separators=(",", ":")).encode("utf-8"))
    signature = _sign(payload)
    return f"{payload}.{signature}"


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> models.User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请先登录")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload_text = _verify_token(token)
        payload = json.loads(payload_text)
        if int(payload.get("exp", 0)) < int(datetime.utcnow().timestamp()):
            raise ValueError("expired")
        user_id = int(payload["sub"])
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已失效，请重新验证邮箱") from exc
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录用户不存在")
    return user


def require_project(db: Session, project_id: str, user: models.User) -> models.Project:
    project = db.get(models.Project, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    return project


def _verify_token(token: str) -> str:
    payload, signature = token.split(".", 1)
    expected = _sign(payload)
    if not hmac.compare_digest(signature, expected):
        raise ValueError("bad signature")
    return _unb64(payload).decode("utf-8")


def _sign(payload: str) -> str:
    digest = hmac.new(AUTH_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return _b64(digest)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))
