import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.config import Config

logger = logging.getLogger(__name__)

FINGERPRINT_FILE = ".last_fingerprint"


def save_local(encrypted_path: str, cfg: Config, fingerprint: str) -> str:
    now = datetime.now(timezone.utc)
    date_dir = os.path.join(cfg.local_backup_path, now.strftime("%Y/%m/%d"))
    os.makedirs(date_dir, exist_ok=True)

    filename = f"vaultwarden-backup-{now.strftime('%Y%m%d-%H%M%S')}.tar.gz.enc"
    dest = os.path.join(date_dir, filename)

    logger.info("Copying backup to %s", dest)
    shutil.copy2(encrypted_path, dest)

    fp_path = os.path.join(cfg.local_backup_path, FINGERPRINT_FILE)
    Path(fp_path).write_text(fingerprint)
    logger.info("Local fingerprint updated")

    return dest


def get_last_local_fingerprint(cfg: Config) -> str | None:
    fp_path = os.path.join(cfg.local_backup_path, FINGERPRINT_FILE)
    if not os.path.isfile(fp_path):
        logger.info("No local fingerprint file found")
        return None
    fingerprint = Path(fp_path).read_text().strip()
    logger.info("Last local fingerprint: %s", fingerprint)
    return fingerprint


MINIMUM_BACKUPS_TO_KEEP = 2


def cleanup_old_local_backups(cfg: Config) -> int:
    if not os.path.isdir(cfg.local_backup_path):
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg.backup_retention_days)
    logger.info("Local cleanup cutoff: %s (retention=%d days)", cutoff.isoformat(), cfg.backup_retention_days)

    base = Path(cfg.local_backup_path)
    all_files = sorted(base.rglob("*.tar.gz.enc"), key=lambda f: f.stat().st_mtime, reverse=True)

    keep = set(all_files[:MINIMUM_BACKUPS_TO_KEEP])

    deleted = 0
    for enc_file in all_files:
        if enc_file in keep:
            logger.info("Keeping recent local backup: %s", enc_file)
            continue
        mtime = datetime.fromtimestamp(enc_file.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            logger.info("Deleting old local backup: %s (mtime: %s)", enc_file, mtime.isoformat())
            enc_file.unlink()
            deleted += 1
            parent = enc_file.parent
            if parent != base and not any(parent.iterdir()):
                parent.rmdir()
                year_dir = parent.parent
                if year_dir != base and not any(year_dir.iterdir()):
                    year_dir.rmdir()

    if deleted:
        logger.info("Cleaned up %d old local backup(s)", deleted)
    else:
        logger.info("No old local local backups to clean up")

    return deleted
