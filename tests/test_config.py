import pytest


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("ENCRYPTION_PASSWORD", raising=False)
    monkeypatch.delenv("S3_ENDPOINT", raising=False)
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.delenv("S3_ACCESS_KEY", raising=False)
    monkeypatch.delenv("S3_SECRET_KEY", raising=False)
    monkeypatch.delenv("S3_REGION", raising=False)
    monkeypatch.delenv("S3_PATH_PREFIX", raising=False)
    monkeypatch.delenv("LOCAL_BACKUP_PATH", raising=False)
    monkeypatch.delenv("VAULTWARDEN_DATA_PATH", raising=False)
    monkeypatch.delenv("BACKUP_RETENTION_DAYS", raising=False)
    monkeypatch.delenv("TMP_DIR", raising=False)
    monkeypatch.delenv("NOTIFY_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("NOTIFY_ON_SUCCESS", raising=False)
    monkeypatch.delenv("NOTIFY_ON_FAILURE", raising=False)


def _base_env(**overrides):
    env = {
        "ENCRYPTION_PASSWORD": "test-password",
        "LOCAL_BACKUP_PATH": "/backups",
    }
    env.update(overrides)
    return env


class TestConfigFromEnv:
    def test_local_only(self, monkeypatch):
        for k, v in _base_env().items():
            monkeypatch.setenv(k, v)
        from src.config import Config

        cfg = Config.from_env()
        assert cfg.local_enabled
        assert not cfg.s3_enabled
        assert cfg.encryption_password == "test-password"
        assert cfg.backup_retention_days == 30
        assert cfg.vaultwarden_data_path == "/data"
        assert cfg.tmp_dir == "/tmp/vw-backup"

    def test_s3_only(self, monkeypatch):
        env = {
            "ENCRYPTION_PASSWORD": "pw",
            "S3_ENDPOINT": "https://s3.example.com",
            "S3_BUCKET": "bucket",
            "S3_ACCESS_KEY": "key",
            "S3_SECRET_KEY": "secret",
        }
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        from src.config import Config

        cfg = Config.from_env()
        assert cfg.s3_enabled
        assert not cfg.local_enabled

    def test_s3_and_local(self, monkeypatch):
        for k, v in _base_env(
            S3_ENDPOINT="https://s3.example.com",
            S3_BUCKET="bucket",
            S3_ACCESS_KEY="key",
            S3_SECRET_KEY="secret",
        ).items():
            monkeypatch.setenv(k, v)
        from src.config import Config

        cfg = Config.from_env()
        assert cfg.s3_enabled
        assert cfg.local_enabled

    def test_missing_encryption_password(self, monkeypatch):
        monkeypatch.setenv("LOCAL_BACKUP_PATH", "/backups")
        from src.config import Config

        with pytest.raises(ValueError, match="ENCRYPTION_PASSWORD"):
            Config.from_env()

    def test_no_destination(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_PASSWORD", "pw")
        from src.config import Config

        with pytest.raises(ValueError, match="At least one backup destination"):
            Config.from_env()

    def test_partial_s3(self, monkeypatch):
        for k, v in _base_env(
            S3_ENDPOINT="https://s3.example.com",
            S3_BUCKET="bucket",
        ).items():
            monkeypatch.setenv(k, v)
        from src.config import Config

        with pytest.raises(ValueError, match="partially configured"):
            Config.from_env()

    def test_retention_days_minimum(self, monkeypatch):
        for k, v in _base_env(BACKUP_RETENTION_DAYS="0").items():
            monkeypatch.setenv(k, v)
        from src.config import Config

        with pytest.raises(ValueError, match="must be >= 1"):
            Config.from_env()

    def test_custom_defaults(self, monkeypatch):
        for k, v in _base_env(
            VAULTWARDEN_DATA_PATH="/custom/data",
            TMP_DIR="/custom/tmp",
            BACKUP_RETENTION_DAYS="7",
            S3_REGION="eu-west-1",
            S3_PATH_PREFIX="my-prefix",
        ).items():
            monkeypatch.setenv(k, v)
        from src.config import Config

        cfg = Config.from_env()
        assert cfg.vaultwarden_data_path == "/custom/data"
        assert cfg.tmp_dir == "/custom/tmp"
        assert cfg.backup_retention_days == 7
        assert cfg.s3_region == "eu-west-1"
        assert cfg.s3_path_prefix == "my-prefix"

    def test_frozen(self, monkeypatch):
        for k, v in _base_env().items():
            monkeypatch.setenv(k, v)
        from src.config import Config

        cfg = Config.from_env()
        with pytest.raises(AttributeError):
            cfg.encryption_password = "new"

    def test_notification_defaults(self, monkeypatch):
        for k, v in _base_env().items():
            monkeypatch.setenv(k, v)
        from src.config import Config

        cfg = Config.from_env()
        assert cfg.notify_webhook_url is None
        assert cfg.notify_on_success is True
        assert cfg.notify_on_failure is True

    def test_notification_configured(self, monkeypatch):
        for k, v in _base_env(
            NOTIFY_WEBHOOK_URL="https://ntfy.sh/mytopic",
            NOTIFY_ON_SUCCESS="false",
            NOTIFY_ON_FAILURE="yes",
        ).items():
            monkeypatch.setenv(k, v)
        from src.config import Config

        cfg = Config.from_env()
        assert cfg.notify_webhook_url == "https://ntfy.sh/mytopic"
        assert cfg.notify_on_success is False
        assert cfg.notify_on_failure is True

    def test_empty_s3_fields_treated_as_none(self, monkeypatch):
        for k, v in _base_env(
            S3_ENDPOINT="",
            S3_BUCKET="",
            S3_ACCESS_KEY="",
            S3_SECRET_KEY="",
        ).items():
            monkeypatch.setenv(k, v)
        from src.config import Config

        cfg = Config.from_env()
        assert not cfg.s3_enabled
        assert cfg.s3_endpoint is None
