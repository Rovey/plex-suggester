# Plex Movie Suggester

Can't decide what to watch? Plex Movie Suggester connects to your [Plex](https://www.plex.tv/) media server, scans your unwatched films, and picks something for you. Three modes to match your mood — **Top Picks**, **Random**, or **Guilty Pleasures**. Works as a CLI tool or a web app you can open on your phone.

## Prerequisites

- **Python 3.11+**
- A **Plex Media Server** with a movie library

## Quick Start

```bash
# Clone and install
git clone https://github.com/Rovey/plex-suggester.git
cd plex-suggester
pip install -e .

# Login to Plex (opens browser for OAuth)
plex-suggest login

# Get a suggestion
plex-suggest movie
```

## Suggestion Modes

| Mode | How it works |
|---|---|
| **Top Picks** (default) | Weighted random — higher rated films have more chance |
| **Random** | Pure random — equal chance for all |
| **Guilty Pleasures** | Inverse-weighted — lower rated films have more chance |

## CLI Usage

```bash
# Single movie
plex-suggest movie [--mode top|random|guilty]

# Marathon by count
plex-suggest marathon --count 4 [--mode top|random|guilty]

# Marathon by time
plex-suggest marathon --hours 8 [--mode top|random|guilty]

# Multi-day planning
plex-suggest multiday --days 3 --hours-per-day 6 [--mode top|random|guilty]

# Exclude a film from future suggestions
plex-suggest exclude add "Film Title" [--reason "watching with someone"]
plex-suggest exclude remove "Film Title"
plex-suggest exclude list

# View suggestion history
plex-suggest history
```

## Web UI

```bash
plex-suggest server [--host localhost] [--port 8000]
```

Open http://localhost:8000 — pick your mode, choose single/marathon/multi-day, and go.

## Docker

Recommended for always-on setups (NAS, Unraid, etc.).

1. Create a `.env` file:

```env
PLEX_TOKEN=your-token-here
PLEX_SERVER_URL=http://your-nas-ip:32400
```

2. Run:

```bash
docker compose up -d
```

The web UI is available at http://localhost:8000.

### Finding Your Plex Token

For headless/Docker setups you need a Plex token. You can find it via:
- Plex Web → any media item → Get Info → View XML → look for `X-Plex-Token` in the URL
- The [official Plex guide](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)

Then set it via the `.env` file above, or directly:

```bash
plex-suggest login --token YOUR_TOKEN
```

## Configuration

All data is stored in `~/.plex-suggester/` (or the path set by `DATA_DIR`):

| File | Contents |
|---|---|
| `config.json` | Plex token and server URL |
| `history.db` | Suggestion history and exclude list |

Environment variables override the config file:

| Variable | Description |
|---|---|
| `PLEX_TOKEN` | Plex authentication token |
| `PLEX_SERVER_URL` | Plex server URL (e.g. `http://192.168.1.100:32400`) |
| `DATA_DIR` | Data directory path (default: `~/.plex-suggester/`) |

## License

[MIT](LICENSE)
