import pytest

from pmail import config


@pytest.fixture(autouse=True)
def temp_dirs(tmp_path, monkeypatch):
    """Never touch the real archive or settings."""
    monkeypatch.setattr(config, "ARCHIVE_DIR", tmp_path / "archive")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    return tmp_path
