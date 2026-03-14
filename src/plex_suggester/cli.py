"""CLI interface — Click commands for plex-suggest."""

from __future__ import annotations

from dataclasses import asdict

import click
import uvicorn

from plex_suggester.auth import login_oauth, login_token
from plex_suggester.engine import (
    SuggestMode,
    Suggestion,
    suggest_by_count,
    suggest_by_time,
    suggest_multiday,
    suggest_single,
)
from plex_suggester.plex_client import Movie, connect, get_unwatched_movies
from plex_suggester.storage import (
    exclude_movie,
    get_excluded_keys,
    get_excluded_movies,
    get_history,
    save_suggestion,
    unexclude_movie,
)

MODE_OPTION = click.option(
    "--mode", "-m",
    type=click.Choice(["top", "random", "guilty"], case_sensitive=False),
    default="top",
    help="Suggestion mode: top (best rated), random, guilty (lower rated).",
)


def _get_filtered_movies() -> list[Movie]:
    """Connect to Plex, fetch unwatched movies, filter out excluded ones."""
    server = connect()
    movies = get_unwatched_movies(server)
    excluded = get_excluded_keys()
    if excluded:
        movies = [m for m in movies if m.rating_key not in excluded]
    if not movies:
        raise SystemExit("No unwatched (non-excluded) movies found in your library.")
    return movies


def _print_suggestion(suggestion: Suggestion, suggestion_type: str) -> None:
    """Pretty-print a suggestion and save it to history."""
    mode_labels = {"top": "🎯 Top Picks", "random": "🎲 Random", "guilty": "🍿 Guilty Pleasures"}
    click.echo(f"\n{mode_labels.get(suggestion.mode.value, suggestion.mode.value)}")
    click.echo("─" * 50)

    if suggestion.days:
        for day in suggestion.days:
            click.echo(f"\n📅 Dag {day.day} ({day.total_display})")
            for movie in day.movies:
                _print_movie(movie)
    else:
        for movie in suggestion.movies:
            _print_movie(movie)

    click.echo(f"\n⏱  Totaal: {suggestion.total_display}")
    click.echo(f"🎬 {len(suggestion.movies)} film(s)")

    # Save to history
    movies_data = [asdict(m) for m in suggestion.movies]
    save_suggestion(suggestion.mode.value, suggestion_type, suggestion.total_minutes, movies_data)


def _print_movie(movie: Movie) -> None:
    rating_str = ""
    if movie.rating is not None:
        rating_str = f" ⭐ {movie.rating:.1f}"
    genres = ", ".join(movie.genres[:3]) if movie.genres else "—"
    click.echo(f"  🎬 {movie.title} ({movie.year or '?'}) — {movie.duration_display}{rating_str}")
    click.echo(f"     {genres}")


@click.group()
def cli():
    """Plex Movie Suggester — smart suggestions from your unwatched library."""
    pass


@cli.command()
@click.option("--token", "-t", default=None, help="Manually provide a Plex auth token.")
def login(token: str | None):
    """Authenticate with Plex (OAuth or manual token)."""
    if token:
        login_token(token)
    else:
        login_oauth()


@cli.command()
@MODE_OPTION
def movie(mode: str):
    """Suggest a single movie."""
    movies = _get_filtered_movies()
    suggestion = suggest_single(movies, SuggestMode(mode))
    _print_suggestion(suggestion, "single")


@cli.command()
@click.option("--count", "-c", default=None, type=int, help="Number of movies.")
@click.option("--hours", "-h", default=None, type=float, help="Time budget in hours.")
@MODE_OPTION
def marathon(count: int | None, hours: float | None, mode: str):
    """Suggest a movie marathon (by count or time)."""
    if count is None and hours is None:
        count = 3  # default

    movies = _get_filtered_movies()

    if hours is not None:
        suggestion = suggest_by_time(movies, hours, SuggestMode(mode))
        _print_suggestion(suggestion, f"marathon-{hours}h")
    else:
        suggestion = suggest_by_count(movies, count, SuggestMode(mode))
        _print_suggestion(suggestion, f"marathon-{count}")


@cli.command()
@click.option("--days", "-d", required=True, type=int, help="Number of days.")
@click.option("--hours-per-day", "-h", required=True, type=float, help="Hours per day.")
@MODE_OPTION
def multiday(days: int, hours_per_day: float, mode: str):
    """Suggest a multi-day movie festival."""
    movies = _get_filtered_movies()
    suggestion = suggest_multiday(movies, days, hours_per_day, SuggestMode(mode))
    _print_suggestion(suggestion, f"multiday-{days}d-{hours_per_day}h")


@cli.group()
def exclude():
    """Manage the exclude list."""
    pass


@exclude.command("add")
@click.argument("title")
@click.option("--reason", "-r", default="", help="Reason for excluding.")
def exclude_add(title: str, reason: str):
    """Exclude a movie from suggestions (search by title)."""
    server = connect()
    movies = get_unwatched_movies(server)

    # Find movie by title (case-insensitive partial match)
    matches = [m for m in movies if title.lower() in m.title.lower()]

    if not matches:
        raise SystemExit(f"No movie found matching '{title}'.")
    elif len(matches) == 1:
        movie = matches[0]
    else:
        click.echo("Multiple matches found:")
        for i, m in enumerate(matches, 1):
            click.echo(f"  {i}. {m.title} ({m.year or '?'})")
        choice = click.prompt("Pick a number", type=int)
        if choice < 1 or choice > len(matches):
            raise SystemExit("Invalid choice.")
        movie = matches[choice - 1]

    exclude_movie(movie.rating_key, movie.title, reason)
    click.echo(f"Excluded: {movie.title} ({movie.year or '?'})")


@exclude.command("remove")
@click.argument("title")
def exclude_remove(title: str):
    """Remove a movie from the exclude list."""
    excluded = get_excluded_movies()
    matches = [e for e in excluded if title.lower() in e["title"].lower()]

    if not matches:
        raise SystemExit(f"No excluded movie found matching '{title}'.")
    elif len(matches) == 1:
        entry = matches[0]
    else:
        click.echo("Multiple matches found:")
        for i, e in enumerate(matches, 1):
            click.echo(f"  {i}. {e['title']}")
        choice = click.prompt("Pick a number", type=int)
        if choice < 1 or choice > len(matches):
            raise SystemExit("Invalid choice.")
        entry = matches[choice - 1]

    unexclude_movie(entry["rating_key"])
    click.echo(f"Removed from exclude list: {entry['title']}")


@exclude.command("list")
def exclude_list():
    """Show all excluded movies."""
    excluded = get_excluded_movies()
    if not excluded:
        click.echo("No excluded movies.")
        return

    click.echo(f"\n🚫 Excluded movies ({len(excluded)}):")
    click.echo("─" * 50)
    for e in excluded:
        reason_str = f" — {e['reason']}" if e["reason"] else ""
        click.echo(f"  {e['title']}{reason_str}")


@cli.command()
@click.option("--limit", "-l", default=20, type=int, help="Number of entries to show.")
def history(limit: int):
    """Show suggestion history."""
    entries = get_history(limit)
    if not entries:
        click.echo("No history yet.")
        return

    mode_labels = {"top": "Top Picks", "random": "Random", "guilty": "Guilty Pleasures"}

    click.echo(f"\n📜 Recent suggestions:")
    click.echo("─" * 50)
    for entry in entries:
        mode_label = mode_labels.get(entry["mode"], entry["mode"])
        movie_titles = ", ".join(m["title"] for m in entry["movies"])
        date = entry["created_at"][:10]
        click.echo(f"  [{date}] {mode_label} | {entry['suggestion_type']} | {movie_titles}")


@cli.command()
@click.option("--host", default="localhost", help="Host to bind to.")
@click.option("--port", "-p", default=8000, type=int, help="Port to bind to.")
def server(host: str, port: int):
    """Start the web UI."""
    click.echo(f"Starting web UI at http://{host}:{port}")
    uvicorn.run("plex_suggester.web.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    cli()
