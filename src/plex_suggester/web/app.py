"""FastAPI web application for Plex Movie Suggester."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from plex_suggester.engine import (
    SuggestMode,
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
    movies = _get_filtered_movies()
    if not movies:
        return templates.TemplateResponse("results.html", {
            "request": request,
            "error": "No unwatched films found (or all are excluded).",
            "suggestion": None,
        })

    suggest_mode = SuggestMode(mode)

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
    exclude_movie(rating_key, title, reason)
    return RedirectResponse("/excluded", status_code=303)


@app.post("/unexclude", response_class=HTMLResponse)
async def exclude_remove(
    request: Request,
    rating_key: str = Form(...),
):
    unexclude_movie(rating_key)
    return RedirectResponse("/excluded", status_code=303)


@app.get("/excluded", response_class=HTMLResponse)
async def excluded_list(request: Request):
    excluded = get_excluded_movies()
    return templates.TemplateResponse("excluded.html", {
        "request": request,
        "excluded": excluded,
    })


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    entries = get_history(50)
    return templates.TemplateResponse("history.html", {
        "request": request,
        "entries": entries,
    })
