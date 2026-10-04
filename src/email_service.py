"""Owner-controlled email access for Personal Nexus.

Uses standard IMAP/SMTP so the integration can work with Gmail and other
providers without storing credentials in the repository. Credentials must be
provided through environment variables.
"""

from __future__ import annotations

import email
import imaplib
import os
import smtplib
from email.header import decode_header
from email.message import EmailMessage
from email.utils import parseaddr


def _decode(value: str | None) -> str:
    if not value:
        return ""
    parts = []
    for fragment, encoding in decode_header(value):
        if isinstance(fragment, bytes):
            parts.append(fragment.decode(encoding or "utf-8", errors="replace"))
        else:
            parts.append(fragment)
    return "".join(parts)


class EmailService:
    """Small, provider-neutral IMAP/SMTP adapter."""

    def __init__(self) -> None:
        self.address = os.getenv("NEXUS_EMAIL_ADDRESS", "")
        self.password = os.getenv("NEXUS_EMAIL_PASSWORD", "")
        self.imap_host = os.getenv("NEXUS_IMAP_HOST", "imap.gmail.com")
        self.imap_port = int(os.getenv("NEXUS_IMAP_PORT", "993"))
        self.smtp_host = os.getenv("NEXUS_SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("NEXUS_SMTP_PORT", "465"))

    def _require_credentials(self) -> None:
        if not self.address or not self.password:
            raise RuntimeError(
                "Nexus email credentials are not configured. "
                "Set NEXUS_EMAIL_ADDRESS and NEXUS_EMAIL_PASSWORD."
            )

    @staticmethod
    def _body(message: email.message.Message) -> str:
        if message.is_multipart():
            chunks = []
            for part in message.walk():
                if part.get_content_type() == "text/plain" and not part.get_filename():
                    payload = part.get_payload(decode=True)
                    if payload:
                        chunks.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
            return "\n".join(chunks).strip()

        payload = message.get_payload(decode=True)
        if isinstance(payload, bytes):
            return payload.decode(message.get_content_charset() or "utf-8", errors="replace").strip()
        return str(payload or "").strip()

    def list_messages(self, mailbox: str = "INBOX", limit: int = 10, unread_only: bool = False) -> list[dict]:
        """Read recent messages. This is read-only."""
        self._require_credentials()
        limit = max(1, min(int(limit), 25))

        with imaplib.IMAP4_SSL(self.imap_host, self.imap_port) as client:
            client.login(self.address, self.password)
            status, _ = client.select(mailbox, readonly=True)
            if status != "OK":
                raise RuntimeError("Email mailbox could not be opened.")

            criteria = "UNSEEN" if unread_only else "ALL"
            status, data = client.search(None, criteria)
            if status != "OK":
                raise RuntimeError("Email search failed.")

            ids = data[0].split()[-limit:]
            messages = []
            for message_id in reversed(ids):
                status, raw = client.fetch(message_id, "(RFC822)")
                if status != "OK" or not raw or not isinstance(raw[0], tuple):
                    continue
                parsed = email.message_from_bytes(raw[0][1])
                sender_name, sender_address = parseaddr(parsed.get("From", ""))
                messages.append(
                    {
                        "id": message_id.decode("ascii", errors="ignore"),
                        "from": _decode(sender_name) or sender_address,
                        "from_address": sender_address,
                        "to": _decode(parsed.get("To", "")),
                        "subject": _decode(parsed.get("Subject", "")),
                        "date": _decode(parsed.get("Date", "")),
                        "body": self._body(parsed)[:6000],
                    }
                )
            return messages

    def send_message(self, to: str, subject: str, body: str) -> dict:
        """Send an email. Nexus permissions should require owner approval."""
        self._require_credentials()
        if not to or "@" not in to:
            raise ValueError("A valid recipient email address is required.")
        if len(subject) > 300 or len(body) > 12000:
            raise ValueError("Email content exceeds safe size limits.")

        message = EmailMessage()
        message["From"] = self.address
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=20) as client:
            client.login(self.address, self.password)
            client.send_message(message)

        return {
            "sent": True,
            "to": to,
            "subject": subject,
            "message": "Email accepted by the configured SMTP server.",
        }
