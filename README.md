# Vaultwarden S3 Backup

Strumento containerizzato per il backup automatico di un'istanza Vaultwarden, con cifratura AES-256-GCM e caricamento su storage S3-compatible e/o salvataggio locale.

## Struttura del progetto

```
vaultwarden-s3-backup/
├── src/
│   ├── main.py        # Entry point del backup
│   ├── decrypt.py     # Tool di decifrazione
│   ├── config.py      # Configurazione da variabili d'ambiente
│   ├── backup.py      # Logica di backup e deduplicazione
│   ├── crypto.py      # Cifratura / decifrazione AES-256-GCM
│   ├── s3.py          # Upload e cleanup su S3
│   └── local.py       # Salvataggio e cleanup in locale
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
├── .env.example
└── .dockerignore
```

| Script | Comando | Descrizione |
|--------|---------|-------------|
| `backup` | `uv run backup` | Esegue il backup completo |
| `decrypt` | `uv run decrypt <input> <output>` | Decifra un file di backup |

## Come funziona

Ogni esecuzione del backup:

1. **Controllo modifiche** — calcola un fingerprint SHA-256 della data directory (path, dimensione e mtime di ogni file) e lo confronta con quello dell'ultimo backup. Se i dati non sono cambiati, salta l'esecuzione
2. **Backup sicuro del database** — usa `sqlite3 .backup` per copiare `db.sqlite3` senza rischio di corruzione
3. **Copia completa dei dati** — copia allegati, sends, configurazione, chiavi RSA e tutto il resto della data directory
4. **Archiviazione** — crea un archivio `tar.gz` in una directory temporanea
5. **Cifratura** — cifra l'archivio con AES-256-GCM (chiave derivata via PBKDF2-SHA256 con 600.000 iterazioni)
6. **Upload / salvataggio** — carica il backup su S3 e/o lo salva in locale, a seconda della configurazione
7. **Pulizia** — elimina automaticamente i backup più vecchi del periodo di retention su ogni destinazione configurata

Il file di backup segue il path:

```
# S3
<prefix>/<YYYY>/<MM>/<DD>/vaultwarden-backup-YYYYMMDD-HHMMSS.tar.gz.enc

# Locale
<local_path>/<YYYY>/<MM>/<DD>/vaultwarden-backup-YYYYMMDD-HHMMSS.tar.gz.enc
```

## Destinazioni

Il tool supporta tre modalità operative:

| Modalità | Configurazione richiesta |
|----------|------------------------|
| **Solo S3** | `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` |
| **Solo locale** | `LOCAL_BACKUP_PATH` |
| **S3 + locale** | Entrambi i set di variabili |

Almeno una destinazione deve essere configurata. Per S3, tutte e quattro le variabili sono obbligatorie.

## Formato del file cifrato

Il file `.enc` è strutturato così:

| Campo | Dimensione | Descrizione |
|-------|-----------|-------------|
| Salt | 16 bytes | Salt casuale per PBKDF2 |
| Nonce | 12 bytes | Nonce per AES-GCM |
| Ciphertext + Tag | variabile | Dati cifrati + tag di autenticazione |

## Deduplicazione

Il tool calcola un fingerprint SHA-256 della data directory di Vaultwarden prima di ogni esecuzione. Il fingerprint è basato su:
- Percorso relativo di ogni file
- Dimensione
- Timestamp di modifica (nanosecondi)

I file `.sqlite3-wal` e `.sqlite3-shm` sono esclusi dal calcolo poiché transitori.

Il fingerprint viene salvato:
- Su S3: come metadata dell'oggetto (`x-amz-meta-fingerprint`)
- In locale: come file `.last_fingerprint` nella root della directory di backup

Se il fingerprint è identico a tutte le destinazioni configurate, il backup viene saltato.

## Esecuzione locale

### Prerequisiti

- [uv](https://docs.astral.sh/uv/) installato
- `sqlite3` disponibile nel PATH

### Setup

```bash
git clone <repo-url>
cd vaultwarden-s3-backup
cp .env.example .env
```

Modifica `.env` con la tua configurazione (vedi [Variabili d'ambiente](#variabili-dambiente)).

### Installa dipendenze

```bash
uv sync
```

### Lancia un backup

```bash
uv run backup
```

### Decifra un backup

```bash
# Con password come argomento
uv run decrypt vaultwarden-backup-20260425-030000.tar.gz.enc backup.tar.gz -p la-tua-password

# Con password da variabile d'ambiente
DECRYPTION_PASSWORD=la-tua-password uv run decrypt vaultwarden-backup-20260425-030000.tar.gz.enc backup.tar.gz
```

Poi estrai l'archivio:

```bash
tar xzf backup.tar.gz -C /path/to/vaultwarden/data
```

## Docker Compose

### 1. Clona e configura

```bash
git clone <repo-url>
cd vaultwarden-s3-backup
cp .env.example .env
```

### 2. Modifica `.env`

```env
# S3 (ometti tutto il blocco per disabilitare)
S3_ENDPOINT=https://s3.example.com
S3_REGION=us-east-1
S3_BUCKET=my-backups
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
S3_PATH_PREFIX=vaultwarden-backups

# Locale (ometti per disabilitare)
LOCAL_BACKUP_PATH=/backups

# Cifratura (obbligatoria)
ENCRYPTION_PASSWORD=una-password-forte

# Vaultwarden
VAULTWARDEN_DATA_PATH=/data

# Retention
BACKUP_RETENTION_DAYS=30

# Cron (sintassi standard)
BACKUP_CRON=0 3 * * *                      # Ogni notte alle 03:00 UTC
```

### 3. Avvia

```bash
docker compose up -d
```

Il `docker-compose.yml` include tre servizi:

| Servizio | Descrizione |
|----------|-------------|
| `vaultwarden` | Istanza Vaultwarden con volume condiviso |
| `backup` | Tool di backup (mount read-only dei dati + volume per backup locali) |
| `ofelia` | Scheduler che esegue il backup secondo il cron configurato |

### Se hai già un'istanza Vaultwarden

Se Vaultwarden è già in esecuzione, rimuovi il servizio `vaultwarden` dal compose e monta il volume esistente:

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

  ofelia:
    image: mcuadros/ofelia:latest
    container_name: ofelia
    command: daemon --docker
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: unless-stopped
```

### Esecuzione manuale

Per lanciare un backup fuori dallo schedule:

```bash
docker compose run --rm backup
```

## Variabili d'ambiente

| Variabile | Obbligatoria | Default | Descrizione |
|-----------|-------------|---------|-------------|
| `ENCRYPTION_PASSWORD` | Sì | — | Password per cifratura |
| `S3_ENDPOINT` | Condizionale | — | Endpoint S3-compatible |
| `S3_BUCKET` | Condizionale | — | Nome del bucket |
| `S3_ACCESS_KEY` | Condizionale | — | Access key |
| `S3_SECRET_KEY` | Condizionale | — | Secret key |
| `S3_REGION` | No | `us-east-1` | Regione |
| `S3_PATH_PREFIX` | No | `vaultwarden-backups` | Prefisso nel bucket |
| `LOCAL_BACKUP_PATH` | Condizionale | — | Path locale per i backup |
| `VAULTWARDEN_DATA_PATH` | No | `/data` | Path dati Vaultwarden |
| `BACKUP_RETENTION_DAYS` | No | `30` | Giorni di retention |
| `BACKUP_CRON` | No | `0 3 * * *` | Schedule cron |
| `TMP_DIR` | No | `/tmp/vw-backup` | Directory temporanea |

> **Nota**: almeno una destinazione tra S3 (tutte le variabili S3\_\*) e locale (`LOCAL_BACKUP_PATH`) deve essere configurata.

## Storage S3-compatible supportati

Qualsiasi servizio compatibile con l'API S3, tra cui:

- AWS S3
- MinIO
- Wasabi
- DigitalOcean Spaces
- Google Cloud Storage (via interoperabilità S3)
- Backblaze B2 (via endpoint S3)
- Ceph RADOS Gateway
