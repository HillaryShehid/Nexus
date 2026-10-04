from email.message import EmailMessage

from src.email_service import EmailService


def test_email_body_plain_text():
    message = EmailMessage()
    message["From"] = "Nexus <nexus@example.com>"
    message["Subject"] = "Hello"
    message.set_content("This is the message body.")

    assert EmailService._body(message) == "This is the message body."


def test_email_service_reads_configuration(monkeypatch):
    monkeypatch.setenv("NEXUS_EMAIL_ADDRESS", "nexus@example.com")
    monkeypatch.setenv("NEXUS_EMAIL_PASSWORD", "local-only")
    service = EmailService()

    assert service.address == "nexus@example.com"
    assert service.password == "local-only"
    assert service.imap_host == "imap.gmail.com"
