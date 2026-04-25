import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    vaultwarden_data_path: str
    encryption_password: str
    backup_retention_days: int
    tmp_dir: str

    s3_endpoint: str | None
    s3_region: str
    s3_bucket: str | None
    s3_access_key: str | None
    s3_secret_key: str | None
    s3_path_prefix: str

    local_backup_path: str | None

    @property
    def s3_enabled(self) -> bool:
        return all(
            [self.s3_endpoint, self.s3_bucket, self.s3_access_key, self.s3_secret_key]
        )

    @property
    def local_enabled(self) -> bool:
        return self.local_backup_path is not None

    @staticmethod
    def from_env() -> "Config":
        encryption_password = os.getenv("ENCRYPTION_PASSWORD", "")
        if not encryption_password:
            raise ValueError("Missing required environment variable: ENCRYPTION_PASSWORD")

        retention = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
        if retention < 1:
            raise ValueError("BACKUP_RETENTION_DAYS must be >= 1")

        s3_endpoint = os.getenv("S3_ENDPOINT") or None
        s3_bucket = os.getenv("S3_BUCKET") or None
        s3_access_key = os.getenv("S3_ACCESS_KEY") or None
        s3_secret_key = os.getenv("S3_SECRET_KEY") or None
        local_backup_path = os.getenv("LOCAL_BACKUP_PATH") or None

        s3_configured = all([s3_endpoint, s3_bucket, s3_access_key, s3_secret_key])
        local_configured = local_backup_path is not None

        if not s3_configured and not local_configured:
            raise ValueError(
                "At least one backup destination is required: "
                "configure S3 (S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY) "
                "and/or local (LOCAL_BACKUP_PATH)"
            )

        if any([s3_endpoint, s3_bucket, s3_access_key, s3_secret_key]) and not s3_configured:
            raise ValueError(
                "S3 is partially configured: all of S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY are required"
            )

        return Config(
            vaultwarden_data_path=os.getenv("VAULTWARDEN_DATA_PATH", "/data"),
            encryption_password=encryption_password,
            backup_retention_days=retention,
            tmp_dir=os.getenv("TMP_DIR", "/tmp/vw-backup"),
            s3_endpoint=s3_endpoint,
            s3_region=os.getenv("S3_REGION", "us-east-1"),
            s3_bucket=s3_bucket,
            s3_access_key=s3_access_key,
            s3_secret_key=s3_secret_key,
            s3_path_prefix=os.getenv("S3_PATH_PREFIX", "vaultwarden-backups"),
            local_backup_path=local_backup_path,
        )
