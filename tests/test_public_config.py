"""Tests for the /config endpoint — the only public-config surface.

The endpoint feeds the browser launch.js script with whatever Plausible
domain + Sentry browser DSN have been set via env vars at deploy time. We
verify three properties:

  * dev default: empty DSN + empty Plausible domain (no third-party loads)
  * prod with both env vars set: both echoed back
  * prod with neither set: still empty (the env-var IS the gate, not the env
    name alone — so a typo in the var doesn't silently send pageviews)

The endpoint must NEVER return values that aren't safe in a browser. The
backend SENTRY_DSN env var is separate (read at module import) and is not
echoed by /config — that prevents accidentally exposing a server-only DSN.

We call the handler function directly (no TestClient) so we do not pull in
httpx as a test dependency; the rest of the suite follows the same pattern.
"""

from __future__ import annotations

import importlib

from app import main as main_module


def _reload_with_env(monkeypatch, env: dict[str, str]):
    """Reset env and reload app.main so the import-time Sentry init runs against
    the patched environment, then return the reloaded module."""

    for key in (
        "APP_ENVIRONMENT", "SENTRY_DSN", "SENTRY_DSN_BROWSER",
        "PLAUSIBLE_DOMAIN", "SENTRY_BROWSER_TRACES_SAMPLE_RATE",
    ):
        monkeypatch.delenv(key, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return importlib.reload(main_module)


def test_dev_default_returns_empty_dsn_and_domain(monkeypatch) -> None:
    """No env vars set → development mode → no third-party loads."""

    mod = _reload_with_env(monkeypatch, {})
    body = mod.public_config()
    assert body["environment"] == "development"
    assert body["sentry_dsn"] == ""
    assert body["plausible_domain"] == ""
    assert "app_version" in body


def test_prod_with_both_set_echoes_them(monkeypatch) -> None:
    """Production mode and the browser DSN + Plausible domain set → echoed."""

    mod = _reload_with_env(monkeypatch, {
        "APP_ENVIRONMENT": "production",
        "SENTRY_DSN_BROWSER": "https://public@o0.ingest.sentry.io/0",
        "PLAUSIBLE_DOMAIN": "propulsionlab.fly.dev",
    })
    body = mod.public_config()
    assert body["environment"] == "production"
    assert body["sentry_dsn"] == "https://public@o0.ingest.sentry.io/0"
    assert body["plausible_domain"] == "propulsionlab.fly.dev"


def test_prod_without_browser_dsn_returns_empty(monkeypatch) -> None:
    """Production mode but no SENTRY_DSN_BROWSER → empty DSN, no browser init.

    Guards against accidentally activating browser Sentry when only the
    server-side SENTRY_DSN is set.
    """

    mod = _reload_with_env(monkeypatch, {
        "APP_ENVIRONMENT": "production",
        "SENTRY_DSN": "https://server-only@o0.ingest.sentry.io/0",
    })
    body = mod.public_config()
    assert body["environment"] == "production"
    assert body["sentry_dsn"] == ""
    assert body["plausible_domain"] == ""


def test_server_sentry_dsn_is_not_echoed(monkeypatch) -> None:
    """The server-side SENTRY_DSN must NEVER leak through /config."""

    mod = _reload_with_env(monkeypatch, {
        "APP_ENVIRONMENT": "production",
        "SENTRY_DSN": "https://server-secret@o0.ingest.sentry.io/0",
    })
    body = mod.public_config()
    assert "server-secret" not in str(body)


def test_traces_sample_rate_defaults_and_overrides(monkeypatch) -> None:
    """traces_sample_rate honours the override env var."""

    mod = _reload_with_env(monkeypatch, {})
    assert mod.public_config()["sentry_traces_sample_rate"] == 0.1

    mod = _reload_with_env(monkeypatch, {
        "SENTRY_BROWSER_TRACES_SAMPLE_RATE": "0.25",
    })
    assert mod.public_config()["sentry_traces_sample_rate"] == 0.25
