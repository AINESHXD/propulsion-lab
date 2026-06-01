"""Day 29 — /pro stub route + deploy artifact sanity checks."""

from __future__ import annotations

from pathlib import Path

from app.main import pro_stub

_ROOT = Path(__file__).resolve().parent.parent


def test_pro_route_serves_existing_file() -> None:
    response = pro_stub()
    assert Path(response.path).exists()
    assert Path(response.path).name == "index.html"


def test_pro_page_is_a_stub_with_no_payment_flow() -> None:
    html = (_ROOT / "app" / "static" / "pro" / "index.html").read_text(encoding="utf-8")
    lowered = html.lower()
    # No actual payment/account machinery (a form, a payment processor).
    assert "<form" not in lowered
    for processor in ("stripe", "paypal", "razorpay", "add to cart"):
        assert processor not in lowered
    # And it states plainly that nothing is collected here.
    assert "no accounts, payments" in lowered


def test_deploy_artifacts_present() -> None:
    for name in ("Dockerfile", ".dockerignore", "fly.toml", "requirements-prod.txt", "DEPLOY.md"):
        assert (_ROOT / name).exists(), f"missing {name}"
