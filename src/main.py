import logging
import sys

from src.config import Config
from src.backup import run_backup


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
        result = run_backup(cfg)
        if result is None:
            sys.exit(0)
    except Exception:
        logger.exception("Backup failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
