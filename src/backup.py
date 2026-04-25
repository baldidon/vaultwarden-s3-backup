import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone

from src.config import Config
from src.crypto import encrypt_file
from src.local import (
    cleanup_old_local_backups,
    get_last_local_fingerprint,
    save_local,
)
from src.s3 import cleanup_old_backups, get_last_backup_fingerprint, upload_file

logger = logging.getLogger(__name__)

DB_FILENAME = "db.sqlite3"
SKIP_EXTENSIONS = {".sqlite3-wal", ".sqlite3-shm"}


def _compute_fingerprint(data_path: str) -> str:
    h = hashlib.sha256()
    for root, dirs, files in sorted(os.walk(data_path)):
        rel_root = os.path.relpath(root, data_path)
        h.update(rel_root.encode())
        for name in sorted(files):
            if any(name.endswith(ext) for ext in SKIP_EXTENSIONS):
                continue
            rel_path = os.path.join(rel_root, name)
            full_path = os.path.join(root, name)
            stat = os.stat(full_path, follow_symlinks=False)
            h.update(rel_path.encode())
            h.update(str(stat.st_size).encode())
            h.update(str(int(stat.st_mtime_ns)).encode())
    return h.hexdigest()


def _safe_sqlite_backup(db_path: str, dest_dir: str) -> None:
    dest_db = os.path.join(dest_dir, DB_FILENAME)
    cmd = f'sqlite3 "{db_path}" ".backup \'{dest_db}\'"'
    logger.info("Running sqlite3 safe backup: %s", cmd)
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"sqlite3 backup failed: {result.stderr}")
    logger.info("sqlite3 backup complete -> %s", dest_db)


def _copy_data_contents(src: str, dst: str) -> None:
    for item in os.listdir(src):
        if item == DB_FILENAME:
            continue
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks=True)
        else:
            shutil.copy2(s, d)


def _create_archive(source_dir: str, output_path: str) -> None:
    result = subprocess.run(
        ["tar", "czf", output_path, "-C", source_dir, "."],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"tar failed: {result.stderr}")


def _has_changed(cfg: Config, fingerprint: str) -> bool:
    if cfg.s3_enabled:
        s3_fp = get_last_backup_fingerprint(cfg)
        if s3_fp != fingerprint:
            return True

    if cfg.local_enabled:
        local_fp = get_last_local_fingerprint(cfg)
        if local_fp != fingerprint:
            return True

    return False


def run_backup(cfg: Config) -> str | None:
    now = datetime.now(timezone.utc)
    logger.info("=== Starting Vaultwarden backup at %s ===", now.isoformat())

    if not os.path.isdir(cfg.vaultwarden_data_path):
        raise FileNotFoundError(
            f"Vaultwarden data directory not found: {cfg.vaultwarden_data_path}"
        )

    db_path = os.path.join(cfg.vaultwarden_data_path, DB_FILENAME)
    if not os.path.isfile(db_path):
        raise FileNotFoundError(f"Vaultwarden database not found: {db_path}")

    logger.info("Computing data fingerprint")
    fingerprint = _compute_fingerprint(cfg.vaultwarden_data_path)
    logger.info("Current fingerprint: %s", fingerprint)

    if not _has_changed(cfg, fingerprint):
        logger.info("No changes detected since last backup. Skipping.")
        return None

    os.makedirs(cfg.tmp_dir, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=cfg.tmp_dir) as staging:
        _safe_sqlite_backup(db_path, staging)
        _copy_data_contents(cfg.vaultwarden_data_path, staging)

        archive_name = f"vw-backup-{now.strftime('%Y%m%d-%H%M%S')}.tar.gz"
        archive_path = os.path.join(cfg.tmp_dir, archive_name)
        encrypted_path = archive_path + ".enc"

        try:
            logger.info("Creating archive %s", archive_path)
            _create_archive(staging, archive_path)

            logger.info("Encrypting archive with AES-256-GCM")
            encrypt_file(archive_path, encrypted_path, cfg.encryption_password)

            destinations = []

            if cfg.s3_enabled:
                s3_key = upload_file(encrypted_path, cfg, fingerprint)
                cleanup_old_backups(cfg)
                destinations.append(f"s3://{cfg.s3_bucket}/{s3_key}")

            if cfg.local_enabled:
                local_path = save_local(encrypted_path, cfg, fingerprint)
                cleanup_old_local_backups(cfg)
                destinations.append(local_path)

            logger.info("=== Backup complete: %s ===", ", ".join(destinations))
            return destinations[0]
        finally:
            for f in (archive_path, encrypted_path):
                if os.path.exists(f):
                    os.remove(f)
