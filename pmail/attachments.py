"""Download one attachment on request. Nothing is saved until an agent or the owner asks.

Files land in archive/attachments/<email id>/ and are never opened or run by this tool.
"""

import email
import email.policy
import re
from pathlib import Path

from pmail import archive, bridge, config

ALL_MAIL = "All Mail"


def safe_name(name: str) -> str:
    """A file name that can't escape its folder or trip Windows/macOS."""
    name = Path(name.replace("\\", "/")).name
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    name = re.sub(r"^(con|prn|aux|nul|com\d|lpt\d)(\.|$)", r"_\1\2", name, flags=re.I)
    return name[:150] or "attachment"


def _find(email_id: str, name: str) -> tuple[dict, dict, int]:
    state = archive.load_state()
    meta = state["messages"].get(email_id)
    if not meta:
        raise SystemExit(f"No email with id {email_id}. Ids are in index.jsonl.")
    matches = [a for a in meta["attachments"] if a["name"] == name] or \
              [a for a in meta["attachments"] if a["name"].lower() == name.lower()]
    if not matches:
        names = ", ".join(a["name"] for a in meta["attachments"]) or "none"
        raise SystemExit(f"That email has no attachment called {name!r}. Its attachments: {names}")
    uid = next((int(u) for u, mid in state["uids"].items() if mid == email_id), None)
    if uid is None:
        raise SystemExit("That email isn't in Bridge's mailbox list yet. Run a sync and try again.")
    return meta, matches[0], uid


def fetch(email_id: str, name: str) -> Path:
    meta, att, uid = _find(email_id, name)
    with bridge.connect() as client:
        client.select_folder(ALL_MAIL, readonly=True)
        data = client.fetch([uid], [b"BODY.PEEK[]"]).get(uid)
    if not data:
        raise SystemExit("Bridge no longer has that email. Run a sync to update the archive.")
    msg = email.message_from_bytes(data[b"BODY[]"], policy=email.policy.default)
    part = next((p for i, p in enumerate(msg.walk()) if i == att["part"]), None)
    if part is None or (part.get_filename() or f"attachment-{att['part']}") != att["name"]:
        raise SystemExit("The email changed since the last sync. Run a sync and try again.")
    folder = config.ARCHIVE_DIR / "attachments" / meta["id"]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / safe_name(att["name"])
    path.write_bytes(part.get_payload(decode=True) or b"")
    return path
