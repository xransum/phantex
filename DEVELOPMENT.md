# Development

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11 | `pyenv install 3.11` |
| uv | latest | https://docs.astral.sh/uv/getting-started/installation/ |
| Node | 22 (LTS) | `nvm install 22 && nvm use 22` |
| bluez | system | `sudo apt install bluez` (Debian/Ubuntu) |

## Setup

```
git clone https://github.com/xransum/phantex
cd phantex

# Python deps
uv sync

# Git hooks
uv run pre-commit install

# Frontend deps + initial build
npm install
npm run build
```

## Running the app

```
uv run flask --app phantex.app:create_app run
```

The app listens on http://localhost:5000.

To enable debug mode:

```
FLASK_DEBUG=1 uv run flask --app phantex.app:create_app run
```

## Frontend development

Rebuild CSS/JS after changing files under `frontend/src/`:

```
npm run build
```

Watch mode (auto-rebuilds on save):

```
npm run watch
```

Built files land in `phantex/static/dist/` and are committed to the repo so
the app works without Node installed.

## Nox sessions

All sessions target Python 3.11 via the `-p` flag.

```
nox -p 3.11 -s lint          # ruff check
nox -p 3.11 -s format        # ruff format --check
nox -p 3.11 -s format -- --fix  # ruff format --fix (apply changes)
nox -p 3.11 -s typecheck     # mypy
nox -p 3.11 -s tests         # pytest + coverage
nox -p 3.11 -s pre-commit    # pre-commit run --all-files
nox -p 3.11                  # runs lint, format, typecheck, tests
```

## Tests

```
uv run pytest tests
uv run pytest tests --cov=phantex --cov-report=term-missing
```

## Bluetooth permissions

BLE scanning works without root via `bleak`.

Classic Bluetooth scanning uses `hcitool scan` which requires the
`CAP_NET_RAW` capability. If classic BT shows a permission warning in the
UI, grant the capability with:

```
sudo setcap cap_net_raw+eip $(which hcitool)
```

Or run the app with `sudo` (not recommended for regular use). If neither is
an option, the app falls back to BLE-only and shows a warning banner on `/bte`.

## Non-uv setup

If you do not have uv installed:

```
pip install -r requirements.txt          # runtime deps
pip install -r requirements-dev.txt      # dev deps
```

Then use `python -m flask` instead of `uv run flask`.

## Project structure

```
phantex/
-- phantex/               Python package
   -- __init__.py         version + CLI entry point
   -- app.py              Flask factory (create_app)
   -- extensions.py       APScheduler instance (unbound)
   -- settings.py         Config classes (Dev/Prod/Testing)
   -- bte/                Bluetooth Terminal Explorer blueprint
      -- __init__.py      Blueprint definition
      -- views.py         GET /bte, GET /bte/data
      -- engine.py        Scan logic + thread-safe device store
      -- tasks.py         APScheduler job
   -- templates/          Jinja2 templates
   -- static/dist/        Vite build output (committed)
-- frontend/              JS/CSS source files
   -- src/css/main.css    Terminal aesthetic styles
   -- src/js/bte.js       BTE polling + DOM update logic
-- tests/                 pytest tests
-- vite.config.js         Vite build config
-- pyproject.toml         Python project + tool config
-- noxfile.py             Nox session definitions
-- .pre-commit-config.yaml  Pre-commit hooks
```
