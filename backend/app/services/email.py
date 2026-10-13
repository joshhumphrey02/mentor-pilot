"""Outbound email: SMTP when configured, otherwise written to the log."""

from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from html import escape
from typing import Protocol

import aiosmtplib
import structlog
from fastapi import BackgroundTasks

from app.core.config import Settings

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    """Dev fallback: prints the email so links can be clicked from the terminal."""

    def __init__(self, *, include_body: bool) -> None:
        # Bodies contain live tokens, so they are never logged outside dev.
        self.include_body = include_body

    async def send(self, message: EmailMessage) -> None:
        if self.include_body:
            # print, not the logger: the logger redacts addresses, and a dev
            # needs to see the whole message.
            print(
                f"\n----- email -----\nTo: {message.to}\nSubject: {message.subject}\n\n"
                f"{message.text}\n-----------------\n",
                flush=True,
            )
        else:
            logger.warning("email.not_sent_smtp_not_configured", subject=message.subject)


class SMTPEmailSender:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, message: EmailMessage) -> None:
        settings = self.settings
        mime = MimeMessage()
        mime["From"] = settings.email_from
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.text)
        mime.add_alternative(message.html, subtype="html")
        await aiosmtplib.send(
            mime,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password.get_secret_value() if settings.smtp_password else None,
            start_tls=settings.smtp_starttls,
            timeout=15,
        )


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.smtp_host:
        return SMTPEmailSender(settings)
    return ConsoleEmailSender(include_body=not settings.is_prod)


class Mailer:
    """Queues email to go out after the response is sent.

    Sending in the background keeps endpoints fast and, for flows that must not
    reveal whether an account exists, keeps response time the same either way.
    """

    def __init__(self, sender: EmailSender, background: BackgroundTasks) -> None:
        self._sender = sender
        self._background = background

    def send_later(self, message: EmailMessage) -> None:
        self._background.add_task(self._deliver, message)

    async def _deliver(self, message: EmailMessage) -> None:
        try:
            await self._sender.send(message)
        except Exception:
            # A failed email must not turn into a 500 after the fact; the user
            # can ask for it to be resent.
            logger.exception("email.send_failed", subject=message.subject)


def _layout(heading: str, paragraphs: list[str], action: tuple[str, str] | None) -> str:
    body = "".join(f'<p style="margin:0 0 16px">{escape(p)}</p>' for p in paragraphs)
    button = ""
    if action:
        label, url = action
        button = (
            f'<p style="margin:24px 0"><a href="{escape(url, quote=True)}" '
            'style="background:#3b43d6;color:#ffffff;text-decoration:none;padding:12px 20px;'
            f'border-radius:10px;font-weight:600;display:inline-block">{escape(label)}</a></p>'
            f'<p style="margin:0 0 16px;font-size:13px;color:#5b6072">Or paste this link into '
            f"your browser:<br>{escape(url)}</p>"
        )
    return (
        '<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;font-size:16px;'
        'line-height:1.5;color:#1c2033;max-width:520px;margin:0 auto;padding:24px">'
        f'<h1 style="font-size:22px;margin:0 0 16px">{escape(heading)}</h1>{body}{button}'
        '<p style="margin:24px 0 0;font-size:13px;color:#5b6072">Mentor Pilot</p></div>'
    )


def _message(
    to: str,
    subject: str,
    heading: str,
    paragraphs: list[str],
    action: tuple[str, str] | None = None,
) -> EmailMessage:
    text_parts = [heading, "", *paragraphs]
    if action:
        text_parts += ["", f"{action[0]}: {action[1]}"]
    return EmailMessage(
        to=to,
        subject=subject,
        text="\n".join(text_parts),
        html=_layout(heading, paragraphs, action),
    )


def first_name(full_name: str) -> str:
    return full_name.split()[0] if full_name.strip() else "there"


def verification_email(to: str, full_name: str, link: str, ttl_hours: int) -> EmailMessage:
    return _message(
        to,
        "Confirm your email for Mentor Pilot",
        f"Welcome, {first_name(full_name)}!",
        [
            "Confirm your email address to start your first project.",
            f"This link works once and expires in {ttl_hours} hours.",
        ],
        ("Confirm my email", link),
    )


def password_reset_email(to: str, full_name: str, link: str, ttl_minutes: int) -> EmailMessage:
    return _message(
        to,
        "Reset your Mentor Pilot password",
        f"Hi {first_name(full_name)},",
        [
            "We got a request to reset your password.",
            f"This link works once and expires in {ttl_minutes} minutes. "
            "If you didn't ask for this, you can ignore this email.",
        ],
        ("Choose a new password", link),
    )


def account_exists_email(to: str, full_name: str, login_link: str) -> EmailMessage:
    return _message(
        to,
        "You already have a Mentor Pilot account",
        f"Hi {first_name(full_name)},",
        [
            "Someone tried to sign up with this email address, but you already have an account.",
            "If that was you, just log in. If you forgot your password, you can reset it "
            "from the login page.",
        ],
        ("Log in", login_link),
    )


def guardian_notice_email(to: str, learner_name: str, privacy_link: str) -> EmailMessage:
    return _message(
        to,
        f"{learner_name} is using Mentor Pilot",
        "A learner listed you as their parent, guardian or teacher",
        [
            f"{learner_name} has joined Mentor Pilot, an AI mentor that guides learners "
            "through science and engineering expo projects, and told us you agree to them "
            "using it.",
            "We store only what is needed to mentor them: their name, school, grade and project "
            "work. If you did not agree, or want their data removed, reply to this email.",
        ],
        ("Read our privacy notice", privacy_link),
    )
