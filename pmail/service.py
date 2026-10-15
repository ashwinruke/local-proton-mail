"""Background work while the tool is running: live mail sync and AI summaries.

Mail: Bridge pushes new-mail notices on INBOX (IMAP IDLE), which trigger a sync
within seconds. A full pass also runs every `sync_minutes` to catch moves,
deletes and label changes, which IDLE on one folder doesn't report.

AI: summarizes pending conversations one at a time, newest first, and picks up
conversations that get new mail.
"""

import collections
import threading
import time
from datetime import datetime

from pmail import ai, bridge, settings, sync

IDLE_CHECK_SECONDS = 30


class Service:
    def __init__(self, summaries: bool = True):
        self.summaries = summaries
        self._stop = threading.Event()
        self._sync_now = threading.Event()
        self._ai_paused = threading.Event()
        self.log_lines: collections.deque[str] = collections.deque(maxlen=200)
        self.status = {
            "mail": "starting",  # starting | syncing | watching | error
            "mail_error": "",
            "last_sync": None,
            "last_result": None,
            "ai": "idle",  # idle | working | paused | off | error
            "ai_error": "",
            "ai_current": "",
        }
        self._threads: list[threading.Thread] = []

    # ------------------------------------------------------------ control

    def start(self) -> None:
        self._threads = [threading.Thread(target=self._mail_loop, name="mail", daemon=True)]
        if self.summaries:
            self._threads.append(threading.Thread(target=self._ai_loop, name="ai", daemon=True))
        for t in self._threads:
            t.start()

    def stop(self) -> None:
        self._stop.set()
        self._sync_now.set()

    def sync_now(self) -> None:
        self._sync_now.set()

    def pause_ai(self, paused: bool) -> None:
        if paused:
            self._ai_paused.set()
        else:
            self._ai_paused.clear()

    def log(self, line: str) -> None:
        stamped = f"{datetime.now():%H:%M:%S}  {line}"
        self.log_lines.append(stamped)
        print(stamped, flush=True)

    # ------------------------------------------------------------ mail

    def _sync(self) -> None:
        self.status["mail"] = "syncing"
        result = sync.run(log=self.log)
        self.status.update(last_sync=datetime.now().isoformat(timespec="seconds"), last_result=result, mail_error="")
        if result["added"] or result["removed"] or result["updated"]:
            self.log(f"Sync: {result['added']} new, {result['updated']} changed, {result['removed']} deleted.")

    def _mail_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._sync()
                self.status["mail"] = "watching"
                self._watch_inbox(settings.load()["sync_minutes"] * 60)
            except (OSError, SystemExit, Exception) as exc:  # Bridge closed, network blip, bad login
                self.status.update(mail="error", mail_error=_plain_error(exc))
                self.log(f"Mail sync paused: {self.status['mail_error']} Retrying in a minute.")
                self._sync_now.wait(60)
            self._sync_now.clear()

    def _watch_inbox(self, seconds: float) -> None:
        """Wait for new mail (IDLE), a Sync-now click, or the next scheduled pass."""
        deadline = time.monotonic() + seconds
        with bridge.connect() as client:
            client.select_folder("INBOX", readonly=True)
            while not self._stop.is_set() and not self._sync_now.is_set() and time.monotonic() < deadline:
                client.idle()
                try:
                    responses = client.idle_check(timeout=IDLE_CHECK_SECONDS)
                finally:
                    client.idle_done()
                if any(len(r) > 1 and r[1] in (b"EXISTS", b"EXPUNGE", b"FETCH") for r in responses):
                    self.log("New activity in INBOX.")
                    return

    # ------------------------------------------------------------ AI

    def _ai_loop(self) -> None:
        while not self._stop.is_set():
            cfg = settings.load()
            if cfg["ai_engine"] == "none":
                self.status["ai"] = "off"
            elif self._ai_paused.is_set():
                self.status["ai"] = "paused"
            else:
                try:
                    self._summarize_some()
                    self.status["ai_error"] = ""
                except Exception as exc:
                    self.status.update(ai="error", ai_error=_plain_error(exc))
            self._stop.wait(60)

    def _summarize_some(self) -> None:
        if ai.ollama_models(settings.load()["ollama_url"]) is None:
            raise RuntimeError("Ollama isn't running. Start the Ollama app to get summaries.")
        from pmail import archive
        todo = ai.pending(archive.load_state()["messages"])
        if not todo:
            self.status.update(ai="idle", ai_current="")
            return
        self.status["ai"] = "working"
        done = 0
        for thread_id, members in todo:
            if self._stop.is_set() or self._ai_paused.is_set() or settings.load()["ai_engine"] == "none":
                break
            self.status["ai_current"] = members[-1]["subject"] or "(no subject)"
            try:
                record = ai.summarize_thread(thread_id, members, settings.load())
                self.log(f"Summarized: {record['title']} ({record['seconds']}s)")
                done += 1
            except RuntimeError as exc:
                if "isn't running" in str(exc) or "isn't installed" in str(exc):
                    raise
                self.log(f"Skipped one conversation: {exc}")
            if done % 10 == 0:
                ai.refresh_indexes()
            if self._sync_now.is_set():
                break  # a fresh sync may have changed what needs summarizing
        if done:
            ai.refresh_indexes()
        self.status.update(ai="idle", ai_current="")


def _plain_error(exc: BaseException) -> str:
    text = str(exc) or exc.__class__.__name__
    if "Can't reach Bridge" in text or isinstance(exc, ConnectionRefusedError):
        return "Proton Mail Bridge isn't running or isn't signed in."
    if "credentials" in text.lower():
        return text
    if "AUTHENTICATIONFAILED" in text or "LOGIN" in text.upper() and "fail" in text.lower():
        return "Bridge rejected the saved password. Copy it again from Bridge in Setup."
    return text
