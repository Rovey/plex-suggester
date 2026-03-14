"""Plex server interaction — connect, discover libraries, fetch unwatched movies."""

from __future__ import annotations

from dataclasses import dataclass

from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer

from plex_suggester.auth import require_token
from plex_suggester.config import load_config


@dataclass
class Movie:
    """Lightweight representation of a Plex movie with relevant metadata."""

    rating_key: str
    title: str
    year: int | None
    duration_minutes: int
    genres: list[str]
    critic_rating: float | None  # Rotten Tomatoes-style (0-10)
    audience_rating: float | None  # IMDb-style (0-10)
    summary: str
    poster_url: str | None
    plex_key: str  # e.g. /library/metadata/12345

    @property
    def rating(self) -> float | None:
        """Best available rating — prefer audience, fallback to critic."""
        return self.audience_rating or self.critic_rating

    @property
    def duration_display(self) -> str:
        hours, minutes = divmod(self.duration_minutes, 60)
        if hours:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"


def connect() -> PlexServer:
    """Connect to the Plex server using stored token + server URL."""
    token = require_token()
    config = load_config()
    server_url = config.get("plex_server_url")

    if server_url:
        return PlexServer(server_url, token)

    # No server URL configured — discover via MyPlexAccount
    account = MyPlexAccount(token=token)
    resources = [r for r in account.resources() if r.provides == "server"]
    if not resources:
        raise SystemExit("No Plex servers found on your account.")

    server = resources[0]
    connection = server.connect()

    # Save server URL for faster reconnection
    config["plex_server_url"] = connection._baseurl
    from plex_suggester.config import save_config
    save_config(config)

    return connection


def get_movie_libraries(server: PlexServer) -> list:
    """Return all movie-type library sections."""
    return [s for s in server.library.sections() if s.type == "movie"]


def get_unwatched_movies(server: PlexServer, library_name: str | None = None) -> list[Movie]:
    """Fetch all unwatched movies from the given library (or first movie library)."""
    libraries = get_movie_libraries(server)
    if not libraries:
        raise SystemExit("No movie libraries found on your Plex server.")

    if library_name:
        section = next((s for s in libraries if s.title == library_name), None)
        if not section:
            available = ", ".join(s.title for s in libraries)
            raise SystemExit(f"Library '{library_name}' not found. Available: {available}")
    else:
        section = libraries[0]

    plex_movies = section.search(unwatched=True)
    return [_to_movie(m, server) for m in plex_movies]


def _to_movie(plex_movie, server: PlexServer) -> Movie:
    """Convert a plexapi Movie object to our Movie dataclass."""
    duration_ms = plex_movie.duration or 0
    duration_minutes = round(duration_ms / 60_000)

    poster_url = None
    if plex_movie.thumb:
        poster_url = server.url(plex_movie.thumb, includeToken=True)

    return Movie(
        rating_key=str(plex_movie.ratingKey),
        title=plex_movie.title,
        year=plex_movie.year,
        duration_minutes=duration_minutes,
        genres=[g.tag for g in plex_movie.genres],
        critic_rating=plex_movie.rating,
        audience_rating=plex_movie.audienceRating,
        summary=plex_movie.summary or "",
        poster_url=poster_url,
        plex_key=plex_movie.key,
    )
