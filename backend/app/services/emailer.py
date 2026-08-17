from __future__ import annotations

import smtplib
from email.message import EmailMessage

import httpx

from app.config import EMAIL_FROM, RESEND_API_KEY, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_TLS, SMTP_USER


class EmailSendError(RuntimeError):
    pass


async def send_login_code(email: str, code: str) -> None:
    subject = "问答审核平台验证码"
    text = f"你的登录验证码是：{code}\n\n验证码 10 分钟内有效。如果不是你本人操作，请忽略这封邮件。"
    html = f"""
    <div style="font-family:Arial,'Microsoft YaHei',sans-serif;line-height:1.7;color:#222">
      <p>你的登录验证码是：</p>
      <p style="font-size:28px;font-weight:700;letter-spacing:4px">{code}</p>
      <p>验证码 10 分钟内有效。如果不是你本人操作，请忽略这封邮件。</p>
    </div>
    """
    if RESEND_API_KEY:
        await _send_resend(email, subject, text, html)
        return
    if SMTP_HOST:
        _send_smtp(email, subject, text, html)
        return
    raise EmailSendError("邮件服务未配置，请在后端环境变量中配置 RESEND_API_KEY 或 SMTP")


async def _send_resend(email: str, subject: str, text: str, html: str) -> None:
    sender = EMAIL_FROM or "QA Review <onboarding@resend.dev>"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={"from": sender, "to": [email], "subject": subject, "text": text, "html": html},
        )
    if response.status_code >= 400:
        raise EmailSendError(response.text)


def _send_smtp(email: str, subject: str, text: str, html: str) -> None:
    if not EMAIL_FROM:
        raise EmailSendError("SMTP 已配置，但 EMAIL_FROM 为空")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = EMAIL_FROM
    message["To"] = email
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
            if SMTP_TLS:
                smtp.starttls()
            if SMTP_USER or SMTP_PASSWORD:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(message)
    except OSError as exc:
        raise EmailSendError(str(exc)) from exc
