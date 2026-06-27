"""E2E test fixtures: live FastAPI server + Playwright browser context.

Uses a minimal FastAPI app with only the TV Screener + health routers
to avoid pre-existing import issues in the full app.
"""

from __future__ import annotations

import multiprocessing
import time
from typing import Generator

import pytest
import uvicorn
from fastapi import FastAPI
from playwright.sync_api import APIRequestContext, Browser, Playwright

from backend.app.api.routers.health import router as health_router
from backend.app.api.routers.tv_screener import router as tv_screener_router


# =========================================================================
# Minimal test app
# =========================================================================


def make_test_app() -> FastAPI:
    """Build a minimal FastAPI app with TV Screener + health routers."""
    app = FastAPI(title="conflu-e2e-test")
    app.include_router(health_router)
    app.include_router(tv_screener_router, prefix="/api/v1")
    return app


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture(scope="session")
def server_url() -> str:
    return "http://localhost:8001"


def run_server() -> None:
    """Run uvicorn with the minimal test app in a subprocess."""
    app = make_test_app()
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")


@pytest.fixture(scope="session")
def test_server() -> Generator[str, None, None]:
    """Start a live uvicorn server in a subprocess for e2e tests.

    Spins up on port 8001 and yields the base URL.
    """
    proc = multiprocessing.Process(target=run_server, daemon=True)
    proc.start()

    url = "http://localhost:8001"
    import urllib.error
    import urllib.request

    deadline = time.monotonic() + 15
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            resp = urllib.request.urlopen(f"{url}/health", timeout=2)
            if resp.status == 200:
                break
        except Exception as e:
            last_err = e
            time.sleep(0.5)
    else:
        raise RuntimeError(f"Server did not start within 15s — {last_err}") from last_err

    yield url
    proc.terminate()
    proc.join(timeout=5)


@pytest.fixture(scope="session")
def playwright() -> Generator[Playwright, None, None]:
    """Create a Playwright instance."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright: Playwright) -> Generator[Browser, None, None]:
    """Launch a Chromium browser instance."""
    browser = playwright.chromium.launch(headless=True)
    yield browser
    browser.close()


@pytest.fixture(scope="session")
def api_context(
    playwright: Playwright,
    test_server: str,
) -> Generator[APIRequestContext, None, None]:
    """Create a Playwright API request context pointed at the test server."""
    context = playwright.request.new_context(base_url=test_server)
    yield context
    context.dispose()
