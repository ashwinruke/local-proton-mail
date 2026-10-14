"""Settings. Credentials live in the OS keychain (Windows Credential Manager / macOS Keychain), never in files."""

import os
from pathlib import Path

import keyring

KEYRING_SERVICE = "local-proton-mail"

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = Path(os.environ.get("PMAIL_ARCHIVE", REPO_ROOT / "archive"))

BRIDGE_HOST = os.environ.get("PMAIL_BRIDGE_HOST", "127.0.0.1")
BRIDGE_IMAP_PORT = int(os.environ.get("PMAIL_BRIDGE_IMAP_PORT", "1143"))


def save_credentials(username: str, password: str) -> None:
    keyring.set_password(KEYRING_SERVICE, "username", username)
    keyring.set_password(KEYRING_SERVICE, "password", password)


def load_credentials() -> tuple[str, str]:
    username = keyring.get_password(KEYRING_SERVICE, "username")
    password = keyring.get_password(KEYRING_SERVICE, "password")
    if not username or not password:
        raise SystemExit("No Bridge credentials saved on this device. Run: python -m pmail setup")
    return username, password
