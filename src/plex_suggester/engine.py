"""Suggestion engine — weighted random selection with three modes."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from plex_suggester.plex_client import Movie

# Default pause between movies in time-based selection
PAUSE_MINUTES = 15


class SuggestMode(str, Enum):
    TOP = "top"
    RANDOM = "random"
    GUILTY = "guilty"


@dataclass
class DayPlan:
    """A single day's movie schedule."""
    day: int
    movies: list[Movie]
    total_minutes: int

    @property
    def total_display(self) -> str:
        hours, minutes = divmod(self.total_minutes, 60)
        return f"{hours}h {minutes}m"


@dataclass
class Suggestion:
    """Result of a suggestion request."""
    mode: SuggestMode
    movies: list[Movie] = field(default_factory=list)
    days: list[DayPlan] | None = None  # Only for multiday
    total_minutes: int = 0

    @property
    def total_display(self) -> str:
        hours, minutes = divmod(self.total_minutes, 60)
        return f"{hours}h {minutes}m"


def _get_weights(movies: list[Movie], mode: SuggestMode) -> list[float]:
    """Calculate selection weights based on mode and ratings."""
    NEUTRAL = 5.0  # Weight for movies with no rating

    if mode == SuggestMode.RANDOM:
        return [1.0] * len(movies)

    weights = []
    for movie in movies:
        rating = movie.rating
        if rating is None:
            weights.append(NEUTRAL)
        elif mode == SuggestMode.TOP:
            # Higher rating = higher weight. Square it to amplify the difference.
            weights.append(max(rating, 0.5) ** 2)
        else:  # GUILTY
            # Invert: lower rating = higher weight
            inverted = max(10.0 - rating, 0.5)
            weights.append(inverted ** 2)

    return weights


def suggest_single(movies: list[Movie], mode: SuggestMode = SuggestMode.TOP) -> Suggestion:
    """Suggest a single movie."""
    if not movies:
        return Suggestion(mode=mode)

    weights = _get_weights(movies, mode)
    selected = random.choices(movies, weights=weights, k=1)
    return Suggestion(
        mode=mode,
        movies=selected,
        total_minutes=selected[0].duration_minutes,
    )


def suggest_by_count(
    movies: list[Movie],
    count: int = 3,
    mode: SuggestMode = SuggestMode.TOP,
) -> Suggestion:
    """Suggest N movies."""
    if not movies:
        return Suggestion(mode=mode)

    count = min(count, len(movies))
    weights = _get_weights(movies, mode)

    selected: list[Movie] = []
    remaining = list(movies)
    remaining_weights = list(weights)

    for _ in range(count):
        pick = random.choices(remaining, weights=remaining_weights, k=1)[0]
        selected.append(pick)
        idx = remaining.index(pick)
        remaining.pop(idx)
        remaining_weights.pop(idx)
        if not remaining:
            break

    total = sum(m.duration_minutes for m in selected) + PAUSE_MINUTES * max(len(selected) - 1, 0)
    return Suggestion(mode=mode, movies=selected, total_minutes=total)


def suggest_by_time(
    movies: list[Movie],
    hours: float,
    mode: SuggestMode = SuggestMode.TOP,
) -> Suggestion:
    """Suggest movies that fit within the given time budget (including pauses)."""
    if not movies:
        return Suggestion(mode=mode)

    max_minutes = hours * 60
    weights = _get_weights(movies, mode)

    selected: list[Movie] = []
    remaining = list(movies)
    remaining_weights = list(weights)
    used_minutes = 0

    while remaining:
        pick = random.choices(remaining, weights=remaining_weights, k=1)[0]
        pause = PAUSE_MINUTES if selected else 0
        needed = pick.duration_minutes + pause

        if used_minutes + needed > max_minutes:
            # Remove this movie and try others
            idx = remaining.index(pick)
            remaining.pop(idx)
            remaining_weights.pop(idx)
            continue

        selected.append(pick)
        used_minutes += needed
        idx = remaining.index(pick)
        remaining.pop(idx)
        remaining_weights.pop(idx)

    return Suggestion(mode=mode, movies=selected, total_minutes=used_minutes)


def suggest_multiday(
    movies: list[Movie],
    days: int,
    hours_per_day: float,
    mode: SuggestMode = SuggestMode.TOP,
) -> Suggestion:
    """Suggest movies spread across multiple days."""
    if not movies:
        return Suggestion(mode=mode)

    remaining_pool = list(movies)
    day_plans: list[DayPlan] = []
    all_selected: list[Movie] = []

    for day_num in range(1, days + 1):
        if not remaining_pool:
            break

        day_suggestion = suggest_by_time(remaining_pool, hours_per_day, mode)

        day_plans.append(DayPlan(
            day=day_num,
            movies=day_suggestion.movies,
            total_minutes=day_suggestion.total_minutes,
        ))
        all_selected.extend(day_suggestion.movies)

        # Remove selected movies from pool
        selected_keys = {m.rating_key for m in day_suggestion.movies}
        remaining_pool = [m for m in remaining_pool if m.rating_key not in selected_keys]

    total = sum(dp.total_minutes for dp in day_plans)
    return Suggestion(mode=mode, movies=all_selected, days=day_plans, total_minutes=total)
