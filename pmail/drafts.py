"""Write drafts into the Proton Drafts folder. This tool cannot send email.

There is deliberately no SMTP code anywhere in this project (a test enforces it).
A draft only becomes an email when the owner opens it in Proton and presses Send.
"""

import email.policy
import email.utils
import re
from email.message import EmailMessage

from pmail import archive, bridge, config

DRAFTS = "Drafts"


def _reply_fields(email_id: str) -> dict:
    meta = archive.load_state()["messages"].get(email_id)
    if not meta:
        raise SystemExit(f"No email with id {email_id}. Ids are in index.jsonl.")
    subject = meta["subject"]
    if not re.match(r"^\s*re\s*:", subject, re.I):
        subject = f"Re: {subject}"
    refs = [r for r in meta.get("refs", []) if r] + ([meta["message_id"]] if meta["message_id"] else [])
    return {
        "to": meta["reply_to"] or meta["from"],
        "subject": subject,
        "in_reply_to": meta["message_id"],
        "references": " ".join(dict.fromkeys(refs)),
    }


def build(sender: str, to: list[str], subject: str, body: str, cc: list[str] | None = None,
          in_reply_to: str = "", references: str = "") -> EmailMessage:
    msg = EmailMessage(policy=email.policy.SMTP)
    msg["From"] = sender
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid()
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    msg.set_content(body)
    return msg


def create(body: str, to: list[str] | None = None, subject: str = "", cc: list[str] | None = None,
           reply_to_id: str | None = None) -> str:
    """Save a draft to Proton's Drafts folder. Returns a short description."""
    if not body.strip():
        raise SystemExit("The draft is empty.")
    fields = _reply_fields(reply_to_id) if reply_to_id else {"to": [], "subject": "", "in_reply_to": "", "references": ""}
    recipients = to or fields["to"]
    if not recipients:
        raise SystemExit("Who is it to? Pass --to, or --reply <email id>.")
    sender, _ = config.load_credentials()
    msg = build(sender, recipients, subject or fields["subject"], body, cc,
                fields["in_reply_to"], fields["references"])
    with bridge.connect() as client:
        client.append(DRAFTS, msg.as_bytes(), flags=[b"\\Draft", b"\\Seen"])
    return f"Draft saved in Proton Drafts: \"{msg['Subject']}\" to {msg['To']}. Open Proton to review and send it."
