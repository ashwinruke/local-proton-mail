import json
import threading
import urllib.error
import urllib.request
from email import message_from_bytes
from http.server import ThreadingHTTPServer

import pytest

from pmail import ai, archive, attachments, config, drafts, lock, server
from pmail.service import Service


def _msg(mid, thread, date, folders=("INBOX",), bulk=False, subject="Hello", body="Hi there"):
    meta = {"id": mid, "proton_id": f"pm-{mid}", "message_id": f"<{mid}@x>", "date": date,
            "from": ["Sam <sam@example.com>"], "to": ["Alex <alex@example.com>"], "cc": [], "reply_to": [],
            "subject": subject, "refs": [], "bulk": bulk, "attachments": [], "folders": list(folders),
            "flags": [], "thread": thread, "snippet": ""}
    meta["path"] = archive.new_path(meta)
    archive.write_message(meta, body)
    return meta


def test_only_personal_threads_outside_spam_and_trash_are_summarized():
    msgs = {m["id"]: m for m in [
        _msg("a1", "a1", "2026-10-01T09:00+00:00"),
        _msg("a2", "a1", "2026-10-02T09:00+00:00", subject="Re: Hello"),
        _msg("b1", "b1", "2026-10-03T09:00+00:00", bulk=True),
        _msg("c1", "c1", "2026-10-04T09:00+00:00", folders=("Trash",)),
        _msg("d1", "d1", "2026-10-05T09:00+00:00", folders=("Spam",)),
    ]}
    eligible = ai.eligible_threads(msgs)
    assert list(eligible) == ["a1"]
    assert [m["id"] for m in eligible["a1"]] == ["a1", "a2"]


def test_pending_tracks_new_mail_in_a_summarized_thread():
    msgs = {"a1": _msg("a1", "a1", "2026-10-01T09:00+00:00")}
    assert [t for t, _ in ai.pending(msgs)] == ["a1"]
    archive.write_json(config.ARCHIVE_DIR / "ai" / "a1.json", {"fingerprint": ai._fingerprint([msgs["a1"]])})
    assert ai.pending(msgs) == []
    msgs["a2"] = _msg("a2", "a1", "2026-10-02T09:00+00:00")
    assert [t for t, _ in ai.pending(msgs)] == ["a1"]


def test_thread_text_keeps_newest_emails_when_too_long(monkeypatch):
    monkeypatch.setattr(ai, "MAX_CHARS", 300)
    members = [_msg(f"m{i}", "m0", f"2026-10-0{i + 1}T09:00+00:00", body=f"email number {i} " + "x" * 100)
               for i in range(4)]
    text, truncated = ai.thread_text(members)
    assert truncated
    assert "email number 3" in text and "email number 0" not in text


def test_summary_records_and_index(monkeypatch):
    msgs = {"a1": _msg("a1", "a1", "2026-10-01T09:00+00:00")}
    fake = {"title": "Lunch plans", "summary": "Sam asks about lunch.", "category": "personal",
            "action_items": [{"task": "Reply to Sam", "owner": "Alex", "due": ""}], "people": ["Sam"],
            "dates": [], "amounts": []}
    monkeypatch.setattr(ai, "_ollama", lambda text, cfg: fake)
    record = ai.summarize_thread("a1", [msgs["a1"]], {"ollama_model": "test"})
    assert record["title"] == "Lunch plans" and record["model"] == "test"
    archive.write_indexes(msgs)
    thread = json.loads((config.ARCHIVE_DIR / "threads.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert thread["summary"] == "Sam asks about lunch."
    assert (config.ARCHIVE_DIR / "AGENTS.md").read_text(encoding="utf-8").count("untrusted") >= 1


def test_attachment_names_cannot_escape_their_folder():
    assert attachments.safe_name("../../evil.exe") == "evil.exe"
    assert attachments.safe_name("..\\..\\boot.ini") == "boot.ini"
    assert attachments.safe_name('re:port<1>.pdf') == "re_port_1_.pdf"
    assert attachments.safe_name("CON.txt") == "_CON.txt"
    assert attachments.safe_name("") == "attachment"


def test_reply_draft_threads_correctly(monkeypatch):
    original = _msg("a1", "a1", "2026-10-01T09:00+00:00", subject="Lunch")
    archive.save_state({**archive.empty_state(), "messages": {"a1": original}})
    fields = drafts._reply_fields("a1")
    assert fields["subject"] == "Re: Lunch"
    assert fields["to"] == ["Sam <sam@example.com>"]
    msg = drafts.build("alex@example.com", fields["to"], fields["subject"], "Friday works.",
                       in_reply_to=fields["in_reply_to"], references=fields["references"])
    parsed = message_from_bytes(msg.as_bytes())
    assert parsed["In-Reply-To"] == "<a1@x>"
    assert parsed["References"] == "<a1@x>"
    assert parsed.get_payload().strip() == "Friday works."


def test_lock_is_reentrant_within_a_thread():
    with lock.archive_lock():
        with lock.archive_lock():
            pass


@pytest.fixture
def page():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(Service(), 0))
    port = httpd.server_address[1]
    httpd.RequestHandlerClass = server.make_handler(Service(), port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


def _req(url, method="GET", headers=None, body=None):
    request = urllib.request.Request(url, method=method, headers=headers or {},
                                     data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(request, timeout=5) as r:
            return r.status, json.loads(r.read() or b"{}") if "json" in r.headers.get("Content-Type", "") else {}
    except urllib.error.HTTPError as exc:
        return exc.code, {}


def test_page_rejects_other_hosts_and_cross_site_posts(page):
    assert _req(f"{page}/api/status")[0] == 200
    assert _req(f"{page}/api/status", headers={"Host": "evil.example.com"})[0] == 403
    assert _req(f"{page}/api/sync", "POST", body={})[0] == 403
    assert _req(f"{page}/api/sync", "POST", {"X-Pmail": "1", "Origin": "https://evil.example.com"}, {})[0] == 403
    assert _req(f"{page}/api/sync", "POST", {"X-Pmail": "1", "Content-Type": "application/json"}, {})[0] == 200


def test_page_settings_validate(page):
    headers = {"X-Pmail": "1", "Content-Type": "application/json"}
    assert _req(f"{page}/api/settings", "POST", headers, {"since": "2026-01-31", "sync_minutes": 999})[0] == 200
    status = _req(f"{page}/api/status")[1]
    assert status["settings"]["since"] == "2026-01-31"
    assert status["settings"]["sync_minutes"] == 120
    assert _req(f"{page}/api/settings", "POST", headers, {"ai_engine": "cloud"})[0] == 400
