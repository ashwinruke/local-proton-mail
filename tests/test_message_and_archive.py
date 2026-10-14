from datetime import datetime, timezone
from email.message import EmailMessage

from pmail import archive, config, message, settings


def _raw(subject="Lunch", sender="Sam <sam@example.com>", body="Friday?", html=None, msgid="<a@x>", refs=None,
         internal="pm-1", headers=None, attachment=None) -> bytes:
    m = EmailMessage()
    m["Subject"] = subject
    m["From"] = sender
    m["To"] = "Alex <alex@example.com>"
    m["Date"] = "Tue, 14 Oct 2026 09:00:00 -0500"
    m["Message-Id"] = msgid
    m["X-Pm-Internal-Id"] = internal
    if refs:
        m["In-Reply-To"] = refs
    for k, v in (headers or {}).items():
        m[k] = v
    m.set_content(body)
    if html:
        m.add_alternative(html, subtype="html")
    if attachment:
        m.add_attachment(b"x" * 2048, maintype="application", subtype="pdf", filename=attachment)
    return m.as_bytes()


NOW = datetime(2026, 10, 14, tzinfo=timezone.utc)


def test_parse_reads_headers_body_and_attachment_names():
    meta, body = message.parse(_raw(attachment="invoice.pdf"), NOW)
    assert meta["subject"] == "Lunch"
    assert meta["from"] == ["Sam <sam@example.com>"]
    assert meta["date"] == "2026-10-14T09:00-05:00"
    assert meta["id"] == message.short_id("pm-1")
    assert meta["bulk"] is False
    assert meta["attachments"] == [{"name": "invoice.pdf", "type": "application/pdf", "size": 2048, "part": 2}]
    assert body == "Friday?"


def test_newsletters_and_notifications_are_bulk():
    assert message.parse(_raw(headers={"List-Unsubscribe": "<mailto:u@x>"}), NOW)[0]["bulk"]
    assert message.parse(_raw(sender="Stripe <notifications@stripe.com>"), NOW)[0]["bulk"]
    assert not message.parse(_raw(sender="Sam <sam@example.com>"), NOW)[0]["bulk"]


def _meta(raw):
    meta, body = message.parse(raw, NOW)
    meta.update(path=archive.new_path(meta), folders=["INBOX"], flags=["unread"], thread=meta["id"], snippet="")
    return meta, body


def test_written_file_has_header_then_text_and_updates_in_place():
    meta, body = _meta(_raw(headers={"List-Id": "news"}))
    archive.write_message(meta, body)
    path = config.ARCHIVE_DIR / meta["path"]
    text = path.read_text(encoding="utf-8")
    assert text.startswith("Subject: Lunch\nFrom: Sam <sam@example.com>\n")
    assert "Folders: INBOX\nFlags: unread\nBulk: yes\n" in text
    assert text.endswith("---\nFriday?\n")
    assert meta["path"] == f"mail/2026/10/2026-10-14_lunch_{meta['id']}.txt"

    meta["folders"] = ["Archive"]
    meta["flags"] = []
    assert archive.refresh_header(meta)
    assert "Folders: Archive\n" in path.read_text(encoding="utf-8")
    assert not archive.refresh_header(meta)


def test_replies_are_grouped_into_one_thread():
    first, _ = _meta(_raw(msgid="<1@x>", internal="pm-1"))
    reply, _ = _meta(_raw(subject="Re: Lunch", msgid="<2@x>", refs="<1@x>", internal="pm-2"))
    other, _ = _meta(_raw(subject="Other", msgid="<3@x>", internal="pm-3"))
    reply["date"] = "2026-10-15T09:00-05:00"
    messages = {m["id"]: m for m in (first, reply, other)}
    archive.assign_threads(messages)
    assert first["thread"] == reply["thread"] == first["id"]
    assert other["thread"] == other["id"]


def test_date_range_setting():
    assert settings.load()["since"] is None
    settings.save({"since": settings.parse_since("2026-01-31")})
    assert settings.load()["since"] == "2026-01-31"
    assert settings.parse_since("all") is None
    assert len(settings.parse_since("today")) == 10
