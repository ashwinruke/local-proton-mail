"""Per-device settings in data/settings.json (gitignored). No secrets here; those live in the keychain."""

import json
import os
from datetime import date

from pmail import config

DEFAULTS = {
    # Keep emails received on or after this date ("YYYY-MM-DD"), or None for all mail.
    "since": None,
}


def _path():
    return config.DATA_DIR / "settings.json"


def load() -> dict:
    path = _path()
    stored = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {**DEFAULTS, **stored}


def save(values: dict) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({**load(), **values}, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def parse_since(value: str) -> str | None:
    """'all' -> None, 'today' -> today's date, 'YYYY-MM-DD' -> that date."""
    value = value.strip().lower()
    if value in ("all", "", "none"):
        return None
    if value == "today":
        return date.today().isoformat()
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise SystemExit(f"Not a date: {value!r}. Use all, today or YYYY-MM-DD.")
