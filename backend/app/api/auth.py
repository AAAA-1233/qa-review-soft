from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import AUTH_CODE_DEV_MODE, AUTH_CODE_EXPIRE_MINUTES
from app.database import get_db
from app.schemas import AuthRequestIn, AuthRequestOut, AuthSessionOut, AuthVerifyIn, UserOut
from app.services.auth import generate_code, get_current_user, hash_code, issue_token, normalize_email
from app.services.emailer import EmailSendError, send_login_code

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/request-code", response_model=AuthRequestOut)
async def request_code(payload: AuthRequestIn, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    code = generate_code()
    login_code = models.EmailLoginCode(
        email=email,
        code_hash=hash_code(email, code),
        expires_at=datetime.utcnow() + timedelta(minutes=AUTH_CODE_EXPIRE_MINUTES),
    )
    db.add(login_code)
    db.commit()
    if not AUTH_CODE_DEV_MODE:
        try:
            await send_login_code(email, code)
        except EmailSendError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return AuthRequestOut(ok=True, expires_in_minutes=AUTH_CODE_EXPIRE_MINUTES, debug_code=code if AUTH_CODE_DEV_MODE else None)


@router.post("/verify-code", response_model=AuthSessionOut)
def verify_code(payload: AuthVerifyIn, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    code_hash = hash_code(email, payload.code)
    login_code = db.scalars(
        select(models.EmailLoginCode)
        .where(
            models.EmailLoginCode.email == email,
            models.EmailLoginCode.consumed_at.is_(None),
        )
        .order_by(models.EmailLoginCode.id.desc())
    ).first()
    if not login_code or login_code.expires_at < datetime.utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码已过期，请重新获取")
    login_code.attempts += 1
    if login_code.attempts > 6:
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码错误次数过多，请重新获取")
    if login_code.code_hash != code_hash:
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码不正确")
    login_code.consumed_at = datetime.utcnow()
    user = db.scalar(select(models.User).where(models.User.email == email))
    if not user:
        user = models.User(email=email)
        db.add(user)
        db.flush()
    user.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return AuthSessionOut(access_token=issue_token(user), user=UserOut(id=user.id, email=user.email))


@router.get("/me", response_model=UserOut)
def me(user: models.User = Depends(get_current_user)):
    return UserOut(id=user.id, email=user.email)
