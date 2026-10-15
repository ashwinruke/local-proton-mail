"""Guards for a public repo that sits next to a private mailbox.

These fail the build if mail, personal data or secrets are ever committed, or if
code that can send email appears.
"""

import re
import subprocess
from pathlib import Path

import pytest

from pmail import archive, config

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_EMAIL_DOMAINS = ("example.com", "example.org", "example.net", "users.noreply.github.com", "anthropic.com",
                         "stripe.com", "x")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,}|x)\b")
SECRETS = re.compile(r"(sk-ant-[A-Za-z0-9_-]{10,}|gh[pousr]_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY)")


def _tracked() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return out.splitlines()


def test_no_mail_or_settings_are_committed():
    bad = [f for f in _tracked() if f.startswith(("archive/", "data/")) or f.endswith((".eml", ".mbox"))]
    assert bad == []


def test_no_real_email_addresses_or_secrets_in_tracked_files():
    problems = []
    for name in _tracked():
        if name.endswith(".lock"):
            continue
        try:
            text = (ROOT / name).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for match in EMAIL.finditer(text):
            if not match.group(1).lower().endswith(ALLOWED_EMAIL_DOMAINS):
                problems.append(f"{name}: {match.group(0)}")
        if SECRETS.search(text):
            problems.append(f"{name}: looks like a secret")
    assert problems == []


def test_tool_has_no_code_that_sends_email():
    for path in (ROOT / "pmail").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\bsmtplib\b|\bSMTP\(|\.send_message\(|\.sendmail\(", text), path.name


def test_archive_in_a_cloud_synced_folder_is_flagged(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ARCHIVE_DIR", tmp_path / "OneDrive" / "archive")
    assert "OneDrive" in archive.cloud_synced_warning()
    monkeypatch.setattr(config, "ARCHIVE_DIR", tmp_path / "projects" / "archive")
    assert archive.cloud_synced_warning() is None
