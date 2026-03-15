"""FastAPI web application for Plex Movie Suggester."""

from __future__ import annotations

import logging
import random
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from plex_suggester.engine import (
    SuggestMode,
    _get_weights,
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

BASE_DIR = Path(__file__).parent
log = logging.getLogger(__name__)
app = FastAPI(title="Plex Movie Suggester")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def _get_filtered_movies() -> list[Movie]:
    server = connect()
    movies = get_unwatched_movies(server)
    excluded = get_excluded_keys()
    if excluded:
        movies = [m for m in movies if m.rating_key not in excluded]
    return movies


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/suggest", response_class=HTMLResponse)
async def suggest(
    request: Request,
    suggestion_type: str = Form(...),
    mode: str = Form("top"),
    count: int = Form(3),
    hours: float = Form(8),
    days: int = Form(3),
    hours_per_day: float = Form(6),
):
    # Clamp inputs to safe ranges
    count = max(1, min(count, 20))
    hours = max(1, min(hours, 24))
    days = max(1, min(days, 14))
    hours_per_day = max(1, min(hours_per_day, 16))

    try:
        movies = _get_filtered_movies()
    except Exception:
        log.exception("Failed to connect to Plex")
        return templates.TemplateResponse("results.html", {
            "request": request,
            "error": "Could not reach your Plex server. Check that it\u2019s running and the connection details are correct.",
            "suggestion": None,
        })

    if not movies:
        return templates.TemplateResponse("results.html", {
            "request": request,
            "error": "No unwatched films left. Try restoring some from your excluded list.",
            "suggestion": None,
        })

    suggest_mode = SuggestMode(mode)

    try:
        if suggestion_type == "single":
            suggestion = suggest_single(movies, suggest_mode)
            type_label = "single"
        elif suggestion_type == "marathon-count":
            suggestion = suggest_by_count(movies, count, suggest_mode)
            type_label = f"marathon-{count}"
        elif suggestion_type == "marathon-time":
            suggestion = suggest_by_time(movies, hours, suggest_mode)
            type_label = f"marathon-{hours}h"
        elif suggestion_type == "multiday":
            suggestion = suggest_multiday(movies, days, hours_per_day, suggest_mode)
            type_label = f"multiday-{days}d-{hours_per_day}h"
        else:
            return RedirectResponse("/", status_code=303)
    except Exception:
        log.exception("Suggestion generation failed")
        return templates.TemplateResponse("results.html", {
            "request": request,
            "error": "Something went wrong. Try shuffling again or pick a different option.",
            "suggestion": None,
        })

    # Save to history
    movies_data = [asdict(m) for m in suggestion.movies]
    save_suggestion(suggest_mode.value, type_label, suggestion.total_minutes, movies_data)

    return templates.TemplateResponse("results.html", {
        "request": request,
        "suggestion": suggestion,
        "suggestion_type": suggestion_type,
        "mode": mode,
        "count": count,
        "hours": hours,
        "days": days,
        "hours_per_day": hours_per_day,
        "error": None,
    })


@app.post("/exclude", response_class=HTMLResponse)
async def exclude_add(
    request: Request,
    rating_key: str = Form(...),
    title: str = Form(...),
    reason: str = Form(""),
):
    # Truncate reason to prevent abuse
    reason = reason[:500].strip()
    exclude_movie(rating_key, title, reason)
    return RedirectResponse("/excluded", status_code=303)


@app.post("/api/exclude-and-replace")
async def exclude_and_replace(
    request: Request,
    rating_key: str = Form(...),
    title: str = Form(...),
    reason: str = Form(""),
    mode: str = Form("top"),
    current_keys: str = Form(""),
):
    """Exclude a movie and return a replacement as rendered HTML."""
    reason = reason[:500].strip()
    exclude_movie(rating_key, title, reason)

    # Parse rating keys of all currently shown movies (to avoid duplicates)
    shown_keys = set(k.strip() for k in current_keys.split(",") if k.strip())
    shown_keys.add(rating_key)  # also exclude the one we just removed

    try:
        movies = _get_filtered_movies()
        # Remove all currently shown movies from the pool
        pool = [m for m in movies if m.rating_key not in shown_keys]
    except Exception:
        log.exception("Failed to connect to Plex for replacement")
        return JSONResponse({"html": "", "error": "Could not reach Plex server."}, status_code=500)

    replacement = None
    if pool:
        suggest_mode = SuggestMode(mode)
        weights = _get_weights(pool, suggest_mode)
        replacement = random.choices(pool, weights=weights, k=1)[0]

    if replacement:
        html = templates.get_template("partials/movie_card.html").render(
            movie=replacement, request=request
        )
        return JSONResponse({"html": html, "rating_key": replacement.rating_key})
    else:
        return JSONResponse({"html": "", "error": "No more movies available."})


@app.post("/api/swap")
async def swap_card(
    request: Request,
    rating_key: str = Form(...),
    mode: str = Form("top"),
    current_keys: str = Form(""),
):
    """Return a replacement movie without excluding the current one."""
    shown_keys = set(k.strip() for k in current_keys.split(",") if k.strip())
    shown_keys.add(rating_key)

    try:
        movies = _get_filtered_movies()
        pool = [m for m in movies if m.rating_key not in shown_keys]
    except Exception:
        log.exception("Failed to connect to Plex for swap")
        return JSONResponse({"html": "", "error": "Could not reach Plex server."}, status_code=500)

    replacement = None
    if pool:
        suggest_mode = SuggestMode(mode)
        weights = _get_weights(pool, suggest_mode)
        replacement = random.choices(pool, weights=weights, k=1)[0]

    if replacement:
        html = templates.get_template("partials/movie_card.html").render(
            movie=replacement, request=request
        )
        return JSONResponse({"html": html, "rating_key": replacement.rating_key})
    else:
        return JSONResponse({"html": "", "error": "No more movies available."})


@app.post("/unexclude", response_class=HTMLResponse)
async def exclude_remove(
    request: Request,
    rating_key: str = Form(...),
):
    unexclude_movie(rating_key)
    return RedirectResponse("/excluded", status_code=303)


@app.get("/excluded", response_class=HTMLResponse)
async def excluded_list(request: Request):
    try:
        excluded = get_excluded_movies()
    except Exception:
        log.exception("Failed to load excluded list")
        excluded = []
    return templates.TemplateResponse("excluded.html", {
        "request": request,
        "excluded": excluded,
    })


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    try:
        entries = get_history(50)
    except Exception:
        log.exception("Failed to load history")
        entries = []
    return templates.TemplateResponse("history.html", {
        "request": request,
        "entries": entries,
    })
