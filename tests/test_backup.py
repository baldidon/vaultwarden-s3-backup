import hashlib
import os
from unittest.mock import patch

import pytest

from src.backup import _compute_fingerprint, _has_changed
from src.config import Config


def _cfg(**overrides):
    defaults = dict(
        vaultwarden_data_path="/data",
        encryption_password="pw",
        backup_retention_days=30,
        tmp_dir="/tmp/vw-backup",
        s3_endpoint=None,
        s3_region="us-east-1",
        s3_bucket=None,
        s3_access_key=None,
        s3_secret_key=None,
        s3_path_prefix="vaultwarden-backups",
        local_backup_path="/backups",
        notify_webhook_url=None,
        notify_on_success=True,
        notify_on_failure=True,
    )
    defaults.update(overrides)
    return Config(**defaults)


class TestComputeFingerprint:
    def test_empty_directory(self, tmp_path):
        fp = _compute_fingerprint(str(tmp_path))
        assert isinstance(fp, str)
        assert len(fp) == 64

    def test_consistent_fingerprint(self, tmp_path):
        (tmp_path / "file.txt").write_text("hello")
        fp1 = _compute_fingerprint(str(tmp_path))
        fp2 = _compute_fingerprint(str(tmp_path))
        assert fp1 == fp2

    def test_changes_on_content_change(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hello")
        fp1 = _compute_fingerprint(str(tmp_path))
        f.write_text("world")
        fp2 = _compute_fingerprint(str(tmp_path))
        assert fp1 != fp2

    def test_changes_on_new_file(self, tmp_path):
        fp1 = _compute_fingerprint(str(tmp_path))
        (tmp_path / "new.txt").write_text("data")
        fp2 = _compute_fingerprint(str(tmp_path))
        assert fp1 != fp2

    def test_skips_wal_files(self, tmp_path):
        (tmp_path / "db.sqlite3").write_text("db")
        (tmp_path / "db.sqlite3-wal").write_text("wal")
        (tmp_path / "db.sqlite3-shm").write_text("shm")

        fp1 = _compute_fingerprint(str(tmp_path))
        (tmp_path / "db.sqlite3-wal").write_text("changed")
        fp2 = _compute_fingerprint(str(tmp_path))

        assert fp1 == fp2

    def test_includes_subdirectories(self, tmp_path):
        sub = tmp_path / "attachments"
        sub.mkdir()
        (sub / "file.dat").write_bytes(b"\x00\x01\x02")

        fp = _compute_fingerprint(str(tmp_path))
        assert isinstance(fp, str)
        assert len(fp) == 64


class TestHasChanged:
    def test_no_previous_s3_fingerprint(self):
        cfg = _cfg(
            s3_endpoint="https://s3.example.com",
            s3_bucket="bucket",
            s3_access_key="key",
            s3_secret_key="secret",
        )
        with patch("src.backup.get_last_backup_fingerprint", return_value=None):
            assert _has_changed(cfg, "abc123") is True

    def test_matching_s3_fingerprint(self):
        cfg = _cfg(
            s3_endpoint="https://s3.example.com",
            s3_bucket="bucket",
            s3_access_key="key",
            s3_secret_key="secret",
            local_backup_path=None,
        )
        with patch("src.backup.get_last_backup_fingerprint", return_value="abc123"):
            assert _has_changed(cfg, "abc123") is False

    def test_different_s3_fingerprint(self):
        cfg = _cfg(
            s3_endpoint="https://s3.example.com",
            s3_bucket="bucket",
            s3_access_key="key",
            s3_secret_key="secret",
        )
        with patch("src.backup.get_last_backup_fingerprint", return_value="old"):
            assert _has_changed(cfg, "new") is True

    def test_no_previous_local_fingerprint(self):
        cfg = _cfg()
        with patch("src.backup.get_last_local_fingerprint", return_value=None):
            assert _has_changed(cfg, "abc123") is True

    def test_matching_local_fingerprint(self):
        cfg = _cfg()
        with patch("src.backup.get_last_local_fingerprint", return_value="abc123"):
            assert _has_changed(cfg, "abc123") is False

    def test_matching_both_destinations(self):
        cfg = _cfg(
            s3_endpoint="https://s3.example.com",
            s3_bucket="bucket",
            s3_access_key="key",
            s3_secret_key="secret",
        )
        with (
            patch("src.backup.get_last_backup_fingerprint", return_value="abc123"),
            patch("src.backup.get_last_local_fingerprint", return_value="abc123"),
        ):
            assert _has_changed(cfg, "abc123") is False

    def test_one_destination_changed(self):
        cfg = _cfg(
            s3_endpoint="https://s3.example.com",
            s3_bucket="bucket",
            s3_access_key="key",
            s3_secret_key="secret",
        )
        with (
            patch("src.backup.get_last_backup_fingerprint", return_value="abc123"),
            patch("src.backup.get_last_local_fingerprint", return_value="old"),
        ):
            assert _has_changed(cfg, "abc123") is True
