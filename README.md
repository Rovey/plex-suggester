# Plex Movie Suggester

Smart movie suggestions from your unwatched Plex library. Three suggestion modes: **Top Picks** (must-see films), **Random**, and **Guilty Pleasures** (trashy fun). CLI + Web UI.

## Quick Start

```bash
# Install
pip install -e .

# Login to Plex (opens browser)
plex-suggest login

# Get a movie suggestion
plex-suggest movie

# Or with a specific mode
plex-suggest movie --mode guilty
```

## CLI Commands

```bash
# Single movie
plex-suggest movie [--mode top|random|guilty]

# Marathon by count
plex-suggest marathon --count 4 [--mode top|random|guilty]

# Marathon by time
plex-suggest marathon --hours 8 [--mode top|random|guilty]

# Multi-day festival
plex-suggest multiday --days 3 --hours-per-day 6 [--mode top|random|guilty]

# Exclude list
plex-suggest exclude add "Film Title" [--reason "watching with someone"]
plex-suggest exclude remove "Film Title"
plex-suggest exclude list

# History
plex-suggest history

# Web UI
plex-suggest server [--host localhost] [--port 8000]
```

## Web UI

Start the web interface:

```bash
plex-suggest server
```

Open http://localhost:8000 — pick your mode, type, and go.

## Docker

```bash
# Set your Plex token and server URL
export PLEX_TOKEN=your-token-here
export PLEX_SERVER_URL=http://your-nas-ip:32400

# Run
docker compose up -d
```

Access the web UI at http://localhost:8000.

### Manual Token

If running headless (Docker/Unraid), set `PLEX_TOKEN` env var or use:

```bash
plex-suggest login --token YOUR_TOKEN
```

You can find your Plex token in Plex Web → Settings → XML view, or via the [official guide](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/).

## Suggestion Modes

| Mode | How it works |
|---|---|
| **Top Picks** (default) | Weighted random — higher rated films have more chance |
| **Random** | Pure random — equal chance for all |
| **Guilty Pleasures** | Weighted random — lower rated films have more chance |

## Configuration

Config is stored in `~/.plex-suggester/` (or `$DATA_DIR`):
- `config.json` — Plex token and server URL
- `history.db` — suggestion history and exclude list

Environment variables override config file:
- `PLEX_TOKEN` — Plex authentication token
- `PLEX_SERVER_URL` — Direct Plex server URL (e.g. `http://192.168.1.100:32400`)
- `DATA_DIR` — Data directory path (default: `~/.plex-suggester/`)
