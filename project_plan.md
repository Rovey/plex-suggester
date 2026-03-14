# Plan: Plex Movie Suggestion Tool

Een Python-applicatie die via Plex OAuth verbindt met je Unraid NAS, je onbekeken films ophaalt, en **slimme suggestielijsten** genereert voor een enkele film, een marathondag, of een meerdaags filmfestival. Drie suggestiemodi: **Top Picks** (gewogen naar hoge rating), **Random**, en **Guilty Pleasures** (gewogen naar lage rating). Films kunnen worden ge-excludet (bijv. "kijk ik samen"). Zowel **CLI als Web UI**. Gegenereerde lijsten worden opgeslagen als geschiedenis.

**Stack:** Python 3.11+ · FastAPI · Jinja2 · SQLite · Click · plexapi

---

### Stappen

**Fase 1 — Project Setup & Plex Connectie**

1. **Project structuur** — `pyproject.toml` met dependencies, folder structuur onder `src/plex_suggester/`, `README.md`
2. **Configuratie** (`config.py`) — data directory configureerbaar via `DATA_DIR` env var (default `~/.plex-suggester/`). Plex-connectie ook via env vars (`PLEX_TOKEN`, `PLEX_SERVER_URL`) als alternatief voor config file — belangrijk voor Docker/Unraid.
3. **Plex OAuth module** (`auth.py`) — OAuth flow via `MyPlexPinLogin`, token opslaan in config file, token herladen bij herstart. Alternatief: directe token-invoer via CLI of env var (voor headless/Docker gebruik).
4. **Plex data module** (`plex_client.py`) — server-connectie, library-detectie, onbekeken films ophalen via `search(unwatched=True)`, metadata extractie (titel, jaar, duur, genres, rating, poster, samenvatting)

**Fase 2 — Suggestie Engine** *(parallel met Fase 3)*

5. **Suggestie engine** (`engine.py`):
   - **Drie suggestiemodi:**
     - **Top Picks** — gewogen random op basis van rating (`movie.rating` / `movie.audienceRating`); hogere rating = meer kans. Voor de "must see" films.
     - **Random** — puur willekeurig, alles gelijke kans.
     - **Guilty Pleasures** — gewogen random naar lagere ratings; voor als je iets trashy wilt.
   - **Selectietypes:**
     - **Enkele film** — 1 film
     - **Marathon op aantal** — N films (standaard 3-4)
     - **Marathon op tijd** — films die passen binnen X uur (met ~15 min pauze tussen films)
     - **Meerdagenplanning** — X dagen × Y uur per dag, films verdeeld over dagen
   - **Shuffle** — niet tevreden? Nieuwe selectie
   - **Exclude list** — ge-exclude films worden gefilterd vóór selectie
6. **Exclude list** (`storage.py`) — SQLite tabel voor ge-exclude films (Plex `ratingKey` + titel + reden). Films op deze lijst verschijnen nooit in suggesties. Beheer via CLI en Web UI (toevoegen, verwijderen, bekijken).
7. **Geschiedenis** (`storage.py`) — SQLite in `$DATA_DIR/history.db`, lijsten opslaan en terugkijken

**Fase 3 — CLI** *(parallel met Fase 2)*

8. **CLI commando's** (`cli.py`):
   - `plex-suggest login` — start OAuth (of `plex-suggest login --token <token>` voor handmatige invoer)
   - `plex-suggest movie [--mode top|random|guilty]` — 1 filmsuggestie
   - `plex-suggest marathon --count 4 [--mode top|random|guilty]` of `--hours 8`
   - `plex-suggest multiday --days 3 --hours-per-day 6 [--mode top|random|guilty]`
   - `plex-suggest exclude add "Film Titel"` — film uitsluiten van suggesties
   - `plex-suggest exclude remove "Film Titel"` — film weer toelaten
   - `plex-suggest exclude list` — alle ge-exclude films tonen
   - `plex-suggest history` — eerdere lijsten
   - `plex-suggest server` — web UI starten

**Fase 4 — Web UI** *(depends on Fase 1-2)*

9. **FastAPI + Jinja2 templates** (`web/`):
   - Hoofdpagina met keuze: enkele film / marathon / meerdagen + modustoggle (Top Picks / Random / Guilty Pleasures)
   - Resultaatpagina met filmkaarten (poster uit Plex, titel, jaar, duur, genre, rating)
   - "Exclude" knop per filmkaart — direct uitsluiten vanuit resultaten
   - Shuffle-knop voor nieuwe suggesties
   - Exclude lijst pagina (beheren, films weer toelaten)
   - Geschiedenis pagina
   - Responsive design

**Fase 5 — Docker / Unraid** *(optioneel, na Fase 4)*

10. **Dockerfile** — multi-stage build, Python 3.11-slim, non-root user, exposed port 8000
11. **docker-compose.yml** — service definitie met environment variables (`PLEX_TOKEN`, `PLEX_SERVER_URL`, `DATA_DIR`) en volume mount voor persistente data (`/data`)
12. **Unraid Community Applications template** (`unraid-template.xml`) — template zodat de container makkelijk via de Unraid UI te installeren is met de juiste port/volume/env var mapping

---

### Projectstructuur

```
20_plex-movie-suggestion/
├── pyproject.toml
├── README.md
├── Dockerfile
├── docker-compose.yml
├── src/plex_suggester/
│   ├── __init__.py
│   ├── config.py          # Configuratie (env vars + config file)
│   ├── auth.py            # Plex OAuth + token opslag
│   ├── plex_client.py     # Plex server interactie
│   ├── engine.py          # Suggestie logica (gewogen + random)
│   ├── storage.py         # SQLite geschiedenis + exclude list
│   ├── cli.py             # Click CLI
│   └── web/
│       ├── app.py         # FastAPI
│       ├── static/style.css
│       └── templates/     # Jinja2 HTML
```

### Verificatie

1. `plex-suggest login` → browser opent → token opgeslagen → herstart → nog ingelogd
2. `plex-suggest movie` → 1 film op basis van standaardmodus (top picks)
3. `plex-suggest movie --mode guilty` → film met lagere rating
4. `plex-suggest marathon --count 4` → 4 films, totale duur getoond
5. `plex-suggest marathon --hours 8` → films passen binnen ~8 uur incl. pauzes
6. `plex-suggest multiday --days 3 --hours-per-day 6` → dagplanning
7. Shuffle geeft andere films
8. `plex-suggest exclude add "The Room"` → film verschijnt niet meer in suggesties
9. `plex-suggest exclude list` → ge-exclude films zichtbaar met reden
10. `plex-suggest exclude remove "The Room"` → film weer beschikbaar
11. `plex-suggest history` → eerdere lijsten zichtbaar
12. Web UI: alle functies werken visueel met filmposters, modustoggle, en exclude-knop per film
13. `PLEX_TOKEN` env var → app start zonder OAuth flow
14. `docker compose up` → web UI beschikbaar op poort 8000, data persistent via volume

### Beslissingen

- **15 min pauze** tussen films bij tijdberekening (aanpasbaar)
- Token persistent in `~/.plex-suggester/config.json` — eenmalig inloggen
- **Drie suggestiemodi** via gewogen randomness — geen harde filters, wel sturing op kwaliteit
- **Gewogen selectie** gebruikt `random.choices(weights=...)` op basis van Plex ratings; films zonder rating krijgen een neutrale gewichtsfactor
- **Standaardmodus: Top Picks** — de meeste gebruikers willen goede films, guilty pleasures is opt-in
- **Exclude list** opgeslagen in SQLite naast geschiedenis — persist tussen sessies
- **Data directory** configureerbaar via `DATA_DIR` env var — default `~/.plex-suggester/`, in Docker typisch `/data`
- **Dual auth** — OAuth voor lokaal gebruik, env var `PLEX_TOKEN` voor Docker/headless
- **Server binding** — `0.0.0.0` in Docker, `localhost` standaard lokaal
- Lokaal draaien zonder Docker, óf als container op Unraid
