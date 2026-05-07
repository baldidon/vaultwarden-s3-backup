import json
import logging
import urllib.error
import urllib.request

from src.config import Config

logger = logging.getLogger(__name__)


def send_notification(cfg: Config, status: str, message: str) -> None:
    if not cfg.notify_webhook_url:
        return

    payload = json.dumps(
        {"status": status, "message": message, "timestamp": _utc_now()}
    ).encode("utf-8")

    req = urllib.request.Request(
        cfg.notify_webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info("Notification sent (%s): HTTP %d", status, resp.status)
    except Exception:
        logger.exception("Failed to send notification")


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
