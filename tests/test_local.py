import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.config import Config
from src.local import (
    cleanup_old_local_backups,
    get_last_local_fingerprint,
    save_local,
)


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
        local_backup_path=None,
        notify_webhook_url=None,
        notify_on_success=True,
        notify_on_failure=True,
    )
    defaults.update(overrides)
    return Config(**defaults)


class TestSaveLocal:
    def test_creates_date_directory(self, tmp_path):
        cfg = _cfg(local_backup_path=str(tmp_path))
        backup_file = tmp_path / "backup.tar.gz.enc"
        backup_file.write_bytes(b"\x00\x01\x02")

        result = save_local(str(backup_file), cfg, "fp123")

        assert os.path.isfile(result)
        assert "vaultwarden-backup-" in result
        assert result.endswith(".tar.gz.enc")

    def test_saves_fingerprint_file(self, tmp_path):
        cfg = _cfg(local_backup_path=str(tmp_path))
        backup_file = tmp_path / "backup.tar.gz.enc"
        backup_file.write_bytes(b"\x00")

        save_local(str(backup_file), cfg, "fp_abc")

        fp_path = tmp_path / ".last_fingerprint"
        assert fp_path.read_text() == "fp_abc"


class TestGetLastLocalFingerprint:
    def test_returns_none_when_no_file(self, tmp_path):
        cfg = _cfg(local_backup_path=str(tmp_path))
        assert get_last_local_fingerprint(cfg) is None

    def test_returns_stored_fingerprint(self, tmp_path):
        cfg = _cfg(local_backup_path=str(tmp_path))
        (tmp_path / ".last_fingerprint").write_text("fp_xyz")

        assert get_last_local_fingerprint(cfg) == "fp_xyz"

    def test_strips_whitespace(self, tmp_path):
        cfg = _cfg(local_backup_path=str(tmp_path))
        (tmp_path / ".last_fingerprint").write_text("  fp_xyz  \n")

        assert get_last_local_fingerprint(cfg) == "fp_xyz"


class TestCleanupOldLocalBackups:
    def test_deletes_old_backups(self, tmp_path):
        cfg = _cfg(local_backup_path=str(tmp_path), backup_retention_days=7)

        old_dir = tmp_path / "2025" / "01" / "01"
        old_dir.mkdir(parents=True)
        old_file = old_dir / "vaultwarden-backup-20250101-030000.tar.gz.enc"
        old_file.write_bytes(b"\x00")

        old_mtime = (datetime.now(timezone.utc) - timedelta(days=10)).timestamp()
        os.utime(old_file, (old_mtime, old_mtime))

        deleted = cleanup_old_local_backups(cfg)
        assert deleted == 1
        assert not old_file.exists()

    def test_keeps_recent_backups(self, tmp_path):
        cfg = _cfg(local_backup_path=str(tmp_path), backup_retention_days=30)

        recent_dir = tmp_path / "2026" / "05" / "01"
        recent_dir.mkdir(parents=True)
        recent_file = recent_dir / "vaultwarden-backup-20260501-030000.tar.gz.enc"
        recent_file.write_bytes(b"\x00")

        deleted = cleanup_old_local_backups(cfg)
        assert deleted == 0
        assert recent_file.exists()

    def test_removes_empty_parent_dirs(self, tmp_path):
        cfg = _cfg(local_backup_path=str(tmp_path), backup_retention_days=7)

        day_dir = tmp_path / "2025" / "01" / "01"
        day_dir.mkdir(parents=True)
        old_file = day_dir / "vaultwarden-backup-old.tar.gz.enc"
        old_file.write_bytes(b"\x00")

        old_mtime = (datetime.now(timezone.utc) - timedelta(days=10)).timestamp()
        os.utime(old_file, (old_mtime, old_mtime))

        cleanup_old_local_backups(cfg)

        assert not day_dir.exists()
        month_dir = tmp_path / "2025" / "01"
        assert not month_dir.exists()

    def test_no_backups_to_clean(self, tmp_path):
        cfg = _cfg(local_backup_path=str(tmp_path))
        assert cleanup_old_local_backups(cfg) == 0

    def test_nonexistent_path(self):
        cfg = _cfg(local_backup_path="/nonexistent/path")
        assert cleanup_old_local_backups(cfg) == 0
