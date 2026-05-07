# AGENTS.md

## Commands

```bash
uv sync --group dev        # install all deps (dev + runtime)
uv run pytest -v           # run tests
uv run backup              # run a backup (needs env vars)
uv run decrypt <in> <out>  # decrypt a backup file
```

No lint or typecheck step is configured.

## Architecture

- **Runtime**: Python 3.12+, managed with `uv`
- **Build backend**: hatchling (`pyproject.toml`)
- **Entry points** (defined in `pyproject.toml [project.scripts]`):
  - `backup` → `src.main:main`
  - `decrypt` → `src.decrypt:main`
- **Package layout**: source lives in `src/`, imported as `src.*` (e.g. `from src.config import Config`)
- **Tests**: `tests/` with pytest, `testpaths = ["tests"]` in `pyproject.toml`

## Key details

- The backup pipeline calls `sqlite3` and `tar` via `subprocess` — these CLIs must be on PATH (the Dockerfile installs `sqlite` via apk)
- All config is env-var based (`Config.from_env()`); no config files. See `.env.example` for the full list
- `ENCRYPTION_PASSWORD` is the only always-required env var; at least one destination (S3 or local) must also be configured
- Dependencies are version-pinned in `pyproject.toml` and locked in `uv.lock`
- Docker container runs `sleep infinity` as entrypoint; Ofelia triggers `uv run backup` on a cron schedule via `docker exec`
- `src/` is the wheel package (`[tool.hatch.build.targets.wheel] packages = ["src"]`)
