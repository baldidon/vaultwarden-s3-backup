import logging
import sys

from src.config import Config
from src.backup import run_backup
from src.notify import send_notification


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main() -> None:
    _setup_logging()
    logger = logging.getLogger(__name__)

    try:
        cfg = Config.from_env()
    except Exception:
        logger.exception("Configuration error")
        sys.exit(1)

    try:
        result = run_backup(cfg)
        if result is None:
            sys.exit(0)
        if cfg.notify_on_success:
            send_notification(cfg, "success", f"Backup complete: {result}")
    except Exception:
        logger.exception("Backup failed")
        if cfg.notify_on_failure:
            send_notification(cfg, "failure", "Backup failed, check container logs for details")
        sys.exit(1)
