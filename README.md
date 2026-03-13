# Phantex

Local OSINT recon terminal. A Flask-based web dashboard that runs on your
laptop and scans for nearby wireless signals. Start with Bluetooth -- more
modules coming.

## Modules

| Path | Name | Status |
|------|------|--------|
| `/bte` | Bluetooth Terminal Explorer | Active |
| `/wte` | Wireless Terminal Explorer | Coming soon |

## Quick start

### With uv (recommended)

```
git clone https://github.com/xransum/phantex
cd phantex
uv sync
uv run flask --app phantex.app:create_app run
```

### Without uv

```
git clone https://github.com/xransum/phantex
cd phantex
pip install -r requirements.txt
flask --app phantex.app:create_app run
```

Open http://localhost:5000 in your browser.

## Requirements

- Python 3.11+
- Linux with `bluez` installed (`hcitool` must be on PATH for classic BT scanning)
- A Bluetooth adapter (BLE scanning works without root; classic BT may need CAP_NET_RAW)

See [DEVELOPMENT.md](DEVELOPMENT.md) for the full development setup.
