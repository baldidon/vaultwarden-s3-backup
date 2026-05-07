import logging
from datetime import datetime, timedelta, timezone

import boto3
from botocore.config import Config as BotoConfig

from src.config import Config

logger = logging.getLogger(__name__)


def _get_client(cfg: Config) -> boto3.client:
    return boto3.client(
        "s3",
        endpoint_url=cfg.s3_endpoint,
        region_name=cfg.s3_region,
        aws_access_key_id=cfg.s3_access_key,
        aws_secret_access_key=cfg.s3_secret_key,
        config=BotoConfig(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def upload_file(local_path: str, cfg: Config, fingerprint: str) -> str:
    now = datetime.now(timezone.utc)
    date_prefix = now.strftime("%Y/%m/%d")
    filename = f"vaultwarden-backup-{now.strftime('%Y%m%d-%H%M%S')}.tar.gz.enc"
    key = f"{cfg.s3_path_prefix}/{date_prefix}/{filename}"

    client = _get_client(cfg)
    logger.info("Uploading %s to s3://%s/%s", local_path, cfg.s3_bucket, key)

    client.upload_file(
        local_path,
        cfg.s3_bucket,
        key,
        ExtraArgs={
            "ContentType": "application/octet-stream",
            "Metadata": {"fingerprint": fingerprint},
        },
    )

    logger.info("Upload complete")
    return key


def get_last_backup_fingerprint(cfg: Config) -> str | None:
    client = _get_client(cfg)
    prefix = cfg.s3_path_prefix + "/"

    paginator = client.get_paginator("list_objects_v2")
    latest_key = None
    latest_date = None

    for page in paginator.paginate(Bucket=cfg.s3_bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if latest_date is None or obj["LastModified"] > latest_date:
                latest_date = obj["LastModified"]
                latest_key = obj["Key"]

    if latest_key is None:
        logger.info("No previous backups found on S3")
        return None

    logger.info("Latest backup: s3://%s/%s", cfg.s3_bucket, latest_key)
    response = client.head_object(Bucket=cfg.s3_bucket, Key=latest_key)
    fingerprint = response.get("Metadata", {}).get("fingerprint")
    if fingerprint:
        logger.info("Last backup fingerprint: %s", fingerprint)
    return fingerprint


MINIMUM_BACKUPS_TO_KEEP = 2


def cleanup_old_backups(cfg: Config) -> int:
    client = _get_client(cfg)
    prefix = cfg.s3_path_prefix + "/"
    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg.backup_retention_days)

    logger.info("Cleanup cutoff: %s (retention=%d days)", cutoff.isoformat(), cfg.backup_retention_days)

    paginator = client.get_paginator("list_objects_v2")
    all_objects = []

    for page in paginator.paginate(Bucket=cfg.s3_bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            all_objects.append(obj)

    all_objects.sort(key=lambda o: o["LastModified"], reverse=True)

    keep = set()
    for obj in all_objects[:MINIMUM_BACKUPS_TO_KEEP]:
        keep.add(obj["Key"])
        logger.info("Keeping recent backup: %s (LastModified: %s)", obj["Key"], obj["LastModified"])

    deleted = 0
    for obj in all_objects:
        if obj["Key"] in keep:
            continue
        last_modified = obj["LastModified"]
        if last_modified.tzinfo is None:
            last_modified = last_modified.replace(tzinfo=timezone.utc)
        if last_modified < cutoff:
            logger.info("Deleting old backup: %s (LastModified: %s)", obj["Key"], last_modified.isoformat())
            client.delete_object(Bucket=cfg.s3_bucket, Key=obj["Key"])
            deleted += 1
        else:
            logger.info("Keeping backup: %s (LastModified: %s)", obj["Key"], last_modified.isoformat())

    if deleted:
        logger.info("Cleaned up %d old backup(s)", deleted)
    else:
        logger.info("No old backups to clean up")

    return deleted
