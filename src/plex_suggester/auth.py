"""Plex OAuth authentication and token management."""

import time
import webbrowser

from plexapi.myplex import MyPlexPinLogin

from plex_suggester.config import load_config, save_config


def login_oauth() -> str:
    """Run Plex OAuth flow — opens browser, waits for user to authenticate.

    Returns the auth token on success.
    """
    pin_login = MyPlexPinLogin(oauth=True)
    oauth_url = pin_login.oauthUrl()

    print(f"Opening browser for Plex login...\n{oauth_url}")
    webbrowser.open(oauth_url)

    print("Waiting for authentication (check your browser)...")
    while not pin_login.checkLogin():
        time.sleep(1)

    if not pin_login.token:
        raise RuntimeError("Plex OAuth failed — no token received.")

    _save_token(pin_login.token)
    print("Login successful! Token saved.")
    return pin_login.token


def login_token(token: str) -> str:
    """Save a manually provided token (for headless/Docker use)."""
    _save_token(token)
    print("Token saved.")
    return token


def get_token() -> str | None:
    """Return the stored Plex token, or None if not authenticated."""
    config = load_config()
    return config.get("plex_token")


def require_token() -> str:
    """Return the stored token or raise an error with instructions."""
    token = get_token()
    if not token:
        raise SystemExit(
            "Not logged in. Run 'plex-suggest login' or set PLEX_TOKEN env var."
        )
    return token


def _save_token(token: str) -> None:
    config = load_config()
    config["plex_token"] = token
    save_config(config)
