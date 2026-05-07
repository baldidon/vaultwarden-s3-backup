import json
from unittest.mock import patch, MagicMock

import pytest

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


class TestSendNotification:
    def test_skips_when_no_url(self):
        from src.notify import send_notification

        cfg = _cfg(notify_webhook_url=None)
        send_notification(cfg, "success", "ok")

    @patch("src.notify.urllib.request.urlopen")
    def test_sends_json_payload(self, mock_urlopen):
        from src.notify import send_notification

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        cfg = _cfg(notify_webhook_url="https://example.com/hook")
        send_notification(cfg, "success", "Backup complete")

        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.get_method() == "POST"
        assert req.full_url == "https://example.com/hook"
        assert req.get_header("Content-type") == "application/json"

        body = json.loads(req.data)
        assert body["status"] == "success"
        assert body["message"] == "Backup complete"
        assert "timestamp" in body

    @patch("src.notify.urllib.request.urlopen", side_effect=Exception("timeout"))
    def test_failure_does_not_raise(self, mock_urlopen):
        from src.notify import send_notification

        cfg = _cfg(notify_webhook_url="https://example.com/hook")
        send_notification(cfg, "failure", "error")
