"""Turn a raw RFC 822 message into plain metadata + stripped text."""

import email
import email.policy
import email.utils
import hashlib
import re
from datetime import datetime, timezone

from pmail import clean

_NOREPLY = re.compile(r"(no-?reply|do-?not-?reply|notifications?|mailer-daemon|newsletter|news|updates?)@", re.I)


def short_id(internal_id: str) -> str:
    """Stable 12-char id derived from Proton's internal message id."""
    return hashlib.sha1(internal_id.encode()).hexdigest()[:12]


def _addresses(msg, header: str) -> list[str]:
    values = msg.get_all(header, [])
    out = []
    for name, addr in email.utils.getaddresses([str(v) for v in values]):
        if addr:
            out.append(f"{name} <{addr}>" if name else addr)
    return out


def _date(msg, fallback: datetime) -> str:
    try:
        dt = email.utils.parsedate_to_datetime(str(msg["Date"]))
    except (TypeError, ValueError, IndexError):
        dt = None
    if dt is None:
        dt = fallback
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat(timespec="minutes")


def _text_of(part) -> str:
    try:
        return part.get_content()
    except (LookupError, UnicodeDecodeError, AssertionError):
        payload = part.get_payload(decode=True) or b""
        return payload.decode("utf-8", "replace")


def _body(msg) -> str:
    plain = html = None
    for part in msg.walk():
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        ctype = part.get_content_type()
        if ctype == "text/plain" and plain is None:
            plain = _text_of(part)
        elif ctype == "text/html" and html is None:
            html = _text_of(part)
    return clean.clean_body(plain, html)


def _attachments(msg) -> list[dict]:
    out = []
    for index, part in enumerate(msg.walk()):
        if part.is_multipart():
            continue
        name = part.get_filename()
        if part.get_content_disposition() != "attachment" and not name:
            continue
        payload = part.get_payload(decode=True) or b""
        out.append({
            "name": name or f"attachment-{index}",
            "type": part.get_content_type(),
            "size": len(payload),
            "part": index,
        })
    return out


def is_bulk(msg) -> bool:
    """Newsletters, marketing and automated notifications (skipped by the AI step)."""
    if msg.get("List-Unsubscribe") or msg.get("List-Id"):
        return True
    if str(msg.get("Precedence", "")).lower() in ("bulk", "list", "junk"):
        return True
    if str(msg.get("Auto-Submitted", "no")).lower() != "no":
        return True
    return bool(_NOREPLY.search(str(msg.get("From", ""))))


def _ids(value) -> list[str]:
    return re.findall(r"<[^<>\s]+>", str(value or ""))


def parse(raw: bytes, internal_date: datetime) -> tuple[dict, str]:
    """Return (metadata, body_text) for one message."""
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    internal_id = str(msg.get("X-Pm-Internal-Id") or msg.get("Message-Id") or hashlib.sha1(raw).hexdigest())
    message_id = (_ids(msg.get("Message-Id")) or [""])[0]
    meta = {
        "id": short_id(internal_id),
        "proton_id": internal_id,
        "message_id": message_id,
        "date": _date(msg, internal_date),
        "from": _addresses(msg, "From"),
        "to": _addresses(msg, "To"),
        "cc": _addresses(msg, "Cc"),
        "reply_to": _addresses(msg, "Reply-To"),
        "subject": str(msg.get("Subject") or "").strip(),
        "refs": _ids(msg.get("References")) + _ids(msg.get("In-Reply-To")),
        "bulk": is_bulk(msg),
        "attachments": _attachments(msg),
    }
    return meta, _body(msg)
