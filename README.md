# Vaultwarden S3 Backup

A containerized tool for automated Vaultwarden backups with AES-256-GCM encryption and upload to S3-compatible storage and/or local storage.

## Project structure

```
vaultwarden-s3-backup/
├── src/
│   ├── main.py        # Backup entry point
│   ├── decrypt.py     # Decryption utility
│   ├── config.py      # Configuration from environment variables
│   ├── backup.py      # Backup logic and deduplication
│   ├── crypto.py      # AES-256-GCM encryption / decryption
│   ├── s3.py          # S3 upload and cleanup
│   ├── local.py       # Local save and cleanup
│   └── notify.py      # Webhook notifications
├── tests/
│   ├── test_config.py
│   ├── test_crypto.py
│   ├── test_notify.py
│   ├── test_backup.py
│   └── test_local.py
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
├── .env.example
└── .dockerignore
```

| Script | Command | Description |
|--------|---------|-------------|
| `backup` | `uv run backup` | Runs a full backup |
| `decrypt` | `uv run decrypt <input> <output>` | Decrypts a backup file |

## How it works

Each backup run:

1. **Change detection** — computes a SHA-256 fingerprint of the data directory (path, size, and mtime of every file) and compares it against the last backup's fingerprint. If nothing changed, the run is skipped
2. **Safe database backup** — uses `sqlite3 .backup` to copy `db.sqlite3` without risk of corruption
3. **Full data copy** — copies attachments, sends, config, RSA keys, and everything else from the data directory
4. **Archiving** — creates a `tar.gz` archive in a temporary directory
5. **Encryption** — encrypts the archive with AES-256-GCM (key derived via PBKDF2-SHA256 with 600,000 iterations)
6. **Upload / save** — uploads the backup to S3 and/or saves it locally, depending on configuration
7. **Cleanup** — automatically deletes backups older than the retention period on each configured destination
8. **Notification** — sends a webhook notification on success, failure, or skip (if configured)

Backup file path:

```
# S3
<prefix>/<YYYY>/<MM>/<DD>/vaultwarden-backup-YYYYMMDD-HHMMSS.tar.gz.enc

# Local
<local_path>/<YYYY>/<MM>/<DD>/vaultwarden-backup-YYYYMMDD-HHMMSS.tar.gz.enc
```

## Destinations

The tool supports three operating modes:

| Mode | Required configuration |
|------|----------------------|
| **S3 only** | `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` |
| **Local only** | `LOCAL_BACKUP_PATH` |
| **S3 + local** | Both sets of variables |

At least one destination must be configured. For S3, all four variables are required.

## Notifications

The tool can send webhook notifications on backup completion, failure, or skip. Set `NOTIFY_WEBHOOK_URL` to any URL that accepts JSON POST requests.

### Payload format

```json
{
  "status": "success | failure | skipped",
  "message": "Backup complete: /backups/2026/05/07/vaultwarden-backup-20260507-030000.tar.gz.enc",
  "timestamp": "2026-05-07T03:00:01.234567+00:00"
}
```

### Compatible services

- [ntfy.sh](https://ntfy.sh) — `NOTIFY_WEBHOOK_URL=https://ntfy.sh/your-topic`
- [Discord](https://support.discord.com/hc/en-us/articles/228383668) — use a Discord webhook URL
- [Slack](https://api.slack.com/messaging/webhooks) — use a Slack webhook URL
- [Gotify](https://gotify.net/) — `NOTIFY_WEBHOOK_URL=https://gotify.example.com/message?token=xxx`
- Any service that accepts JSON POST

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NOTIFY_WEBHOOK_URL` | — | Webhook URL (omit to disable) |
| `NOTIFY_ON_SUCCESS` | `true` | Notify on successful backup or skip |
| `NOTIFY_ON_FAILURE` | `true` | Notify on backup failure |

## Encrypted file format

The `.enc` file is structured as follows:

| Field | Size | Description |
|-------|------|-------------|
| Salt | 16 bytes | Random salt for PBKDF2 |
| Nonce | 12 bytes | Nonce for AES-GCM |
| Ciphertext + Tag | variable | Encrypted data + authentication tag |

## Deduplication

The tool computes a SHA-256 fingerprint of the Vaultwarden data directory before each run. The fingerprint is based on:
- Relative path of every file
- File size
- Modification timestamp (nanoseconds)

`.sqlite3-wal` and `.sqlite3-shm` files are excluded from the calculation since they are transient.

The fingerprint is stored:
- On S3: as object metadata (`x-amz-meta-fingerprint`)
- Locally: as a `.last_fingerprint` file in the backup directory root

If the fingerprint matches all configured destinations, the backup is skipped.

## Running locally

### Prerequisites

- [uv](https://docs.astral.sh/uv/) installed
- `sqlite3` available in PATH

### Setup

```bash
git clone <repo-url>
cd vaultwarden-s3-backup
cp .env.example .env
```

Edit `.env` with your configuration (see [Environment variables](#environment-variables)).

### Install dependencies

```bash
uv sync
```

### Run a backup

```bash
uv run backup
```

### Decrypt a backup

```bash
# With password as argument
uv run decrypt vaultwarden-backup-20260425-030000.tar.gz.enc backup.tar.gz -p your-password

# With password from environment variable
DECRYPTION_PASSWORD=your-password uv run decrypt vaultwarden-backup-20260425-030000.tar.gz.enc backup.tar.gz
```

Then extract the archive:

```bash
tar xzf backup.tar.gz -C /path/to/vaultwarden/data
```

## Docker Compose

### 1. Clone and configure

```bash
git clone <repo-url>
cd vaultwarden-s3-backup
cp .env.example .env
```

### 2. Edit `.env`

```env
# S3 (omit the entire block to disable)
S3_ENDPOINT=https://s3.example.com
S3_REGION=us-east-1
S3_BUCKET=my-backups
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
S3_PATH_PREFIX=vaultwarden-backups

# Local (omit to disable)
LOCAL_BACKUP_PATH=/backups

# Encryption (required)
ENCRYPTION_PASSWORD=a-strong-password

# Vaultwarden
VAULTWARDEN_DATA_PATH=/data

# Retention
BACKUP_RETENTION_DAYS=30

# Cron (standard cron syntax)
BACKUP_CRON=0 3 * * *                      # Every night at 03:00 UTC

# Notifications (optional)
NOTIFY_WEBHOOK_URL=https://ntfy.sh/your-topic
```

### 3. Start

```bash
docker compose up -d
```

The `docker-compose.yml` includes three services:

| Service | Description |
|---------|-------------|
| `vaultwarden` | Vaultwarden instance with shared volume |
| `backup` | Backup tool (stays idle, Ofelia triggers backups via `docker exec`) |
| `ofelia` | Scheduler that runs backups according to the configured cron |

The `backup` container has a healthcheck (`pgrep -f sleep`) and Ofelia waits for it to be healthy before starting.

### Using an existing Vaultwarden instance

If Vaultwarden is already running, remove the `vaultwarden` service from the compose file and mount the existing volume:

```yaml
services:
  backup:
    build: .
    container_name: vw-backup
    env_file: .env
    volumes:
      - vw-data:/data:ro
      - vw-backups:/backups
    labels:
      ofelia.enabled: "true"
      ofelia.job-exec.vw-backup: "uv run backup"
      ofelia.job-exec.vw-backup.schedule: "${BACKUP_CRON:-0 3 * * *}"
    healthcheck:
      test: ["CMD", "pgrep", "-f", "sleep"]
      interval: 1m
      timeout: 5s
      retries: 3
      start_period: 10s
    restart: unless-stopped

  ofelia:
    image: mcuadros/ofelia:latest
    container_name: ofelia
    command: daemon --docker
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    depends_on:
      backup:
        condition: service_healthy
    restart: unless-stopped
```

### Manual run

To trigger a backup outside of the schedule:

```bash
docker compose exec vw-backup uv run backup
```

## Testing

```bash
uv sync --group dev
uv run pytest -v
```

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENCRYPTION_PASSWORD` | Yes | — | Password for encryption |
| `S3_ENDPOINT` | Conditional | — | S3-compatible endpoint |
| `S3_BUCKET` | Conditional | — | Bucket name |
| `S3_ACCESS_KEY` | Conditional | — | Access key |
| `S3_SECRET_KEY` | Conditional | — | Secret key |
| `S3_REGION` | No | `us-east-1` | Region |
| `S3_PATH_PREFIX` | No | `vaultwarden-backups` | Path prefix in the bucket |
| `LOCAL_BACKUP_PATH` | Conditional | — | Local path for backups |
| `VAULTWARDEN_DATA_PATH` | No | `/data` | Vaultwarden data path |
| `BACKUP_RETENTION_DAYS` | No | `30` | Retention period in days |
| `BACKUP_CRON` | No | `0 3 * * *` | Cron schedule |
| `TMP_DIR` | No | `/tmp/vw-backup` | Temporary directory |
| `NOTIFY_WEBHOOK_URL` | No | — | Webhook URL for notifications |
| `NOTIFY_ON_SUCCESS` | No | `true` | Notify on success/skip |
| `NOTIFY_ON_FAILURE` | No | `true` | Notify on failure |

> **Note**: at least one destination between S3 (all `S3_*` variables) and local (`LOCAL_BACKUP_PATH`) must be configured.

## Supported S3-compatible storage

Any service compatible with the S3 API, including:

- AWS S3
- MinIO
- Wasabi
- DigitalOcean Spaces
- Google Cloud Storage (via S3 interoperability)
- Backblaze B2 (via S3 endpoint)
- Ceph RADOS Gateway
