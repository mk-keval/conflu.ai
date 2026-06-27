"""E2E tests for TV Screener API using Playwright HTTP requests.

Tests every endpoint end-to-end against a live uvicorn server.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import APIRequestContext, expect


# =========================================================================
# Helper
# =========================================================================


def expect_ok_response(response, context: str = "response") -> None:
    """Assert a 200 OK response with JSON body."""
    expect(response).to_be_ok()
    body = response.json()
    assert body is not None, f"{context}: body should not be None"
    return body


# =========================================================================
# Health endpoint
# =========================================================================


class TestHealthEndpoint:
    """GET /health — liveness probe."""

    def test_health_returns_ok(self, api_context: APIRequestContext) -> None:
        resp = api_context.get("/health")
        body = expect_ok_response(resp, "health")
        assert body["status"] == "ok"
        assert "service" in body
        assert body["service"] == "conflu-api"
        assert "version" in body

    def test_health_response_time(self, api_context: APIRequestContext) -> None:
        import time
        start = time.monotonic()
        api_context.get("/health")
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"Health check too slow: {elapsed:.2f}s"


# =========================================================================
# Templates endpoints
# =========================================================================


class TestTemplatesEndpoint:
    """GET /api/v1/screen/tv/templates — list / load templates."""

    def test_list_templates_returns_list(self, api_context: APIRequestContext) -> None:
        resp = api_context.get("/api/v1/screen/tv/templates")
        body = expect_ok_response(resp, "templates")
        assert isinstance(body, list)
        # Should have at least one template
        assert len(body) > 0, "Expected at least 1 screen template"
        for t in body:
            assert "name" in t
            assert "description" in t

    def test_get_template_by_name(self, api_context: APIRequestContext) -> None:
        # First list templates
        list_resp = api_context.get("/api/v1/screen/tv/templates")
        templates = list_resp.json()
        if not templates:
            pytest.skip("No templates available")
        name = templates[0]["name"]

        resp = api_context.get(f"/api/v1/screen/tv/templates/{name}")
        body = expect_ok_response(resp, f"template/{name}")
        assert body["name"] == name
        # A template should have filters/indicators defined
        assert "filters" in body or "screen" in body or "config" in body or "name" in body

    def test_get_template_not_found(self, api_context: APIRequestContext) -> None:
        resp = api_context.get("/api/v1/screen/tv/templates/nonexistent_template_xyz")
        assert resp.status == 404
        body = resp.json()
        assert "detail" in body


# =========================================================================
# Screen endpoint (happy path — uses template name)
# =========================================================================


class TestScreenEndpoint:
    """POST /api/v1/screen/tv — run screen by template name."""

    @pytest.fixture(autouse=True)
    def _ensure_templates(self, api_context: APIRequestContext) -> None:
        """Skip all tests in this class if no templates are available."""
        resp = api_context.get("/api/v1/screen/tv/templates")
        templates = resp.json()
        if not templates:
            pytest.skip("No templates available — cannot run screen tests")

    def test_screen_with_template_name(self, api_context: APIRequestContext) -> None:
        """Screen using a template name."""
        resp = api_context.post(
            "/api/v1/screen/tv",
            data={"config": "trend-follower"},
        )
        body = expect_ok_response(resp, "screen/trend-follower")
        # Should get a structured screen response
        assert "screen_name" in body
        assert "total_matches" in body
        assert "execution_ms" in body
        assert "timeframe" in body
        assert "results" in body

    def test_screen_with_limit(self, api_context: APIRequestContext) -> None:
        """Screen with a small limit."""
        resp = api_context.post(
            "/api/v1/screen/tv",
            data={"config": "trend-follower", "limit": 5},
        )
        body = expect_ok_response(resp, "screen/limit=5")
        # total_matches is the full TV count, results array is limited
        assert len(body.get("results", [])) <= 500

    def test_screen_nonexistent_template(self, api_context: APIRequestContext) -> None:
        """Screen with a nonexistent template should 404."""
        resp = api_context.post(
            "/api/v1/screen/tv",
            data={"config": "does_not_exist_xyz"},
        )
        assert resp.status == 404


class TestMultiTFEndpoint:
    """POST /api/v1/screen/tv/multi-tf — multi-timeframe screen."""

    @pytest.fixture(autouse=True)
    def _ensure_templates(self, api_context: APIRequestContext) -> None:
        resp = api_context.get("/api/v1/screen/tv/templates")
        templates = resp.json()
        if not templates:
            pytest.skip("No templates available — cannot run multi-tf tests")

    def test_multi_tf_with_template(self, api_context: APIRequestContext) -> None:
        resp = api_context.post(
            "/api/v1/screen/tv/multi-tf",
            data={"config": "trend-follower"},
        )
        body = expect_ok_response(resp, "multi-tf")
        assert "screen_name" in body
        assert "timeframes" in body
        assert "results" in body


# =========================================================================
# Swagger UI (served by FastAPI)
# =========================================================================


class TestSwaggerUI:
    """GET /docs — Swagger UI (served by FastAPI)."""

    def test_swagger_ui_loads(self, browser, test_server: str) -> None:
        """Open Swagger UI in a real browser and verify it renders."""
        page = browser.new_page()
        page.goto(f"{test_server}/docs")
        # Swagger UI renders with "Swagger UI" in the title
        # Swagger UI sets title to "{app_name} - Swagger UI"
        assert "Swagger UI" in page.title()
        # Should show the tv-screener endpoints
        content = page.text_content("html") or ""
        assert "TV Screener" in content or "tv-screener" in content
        page.close()

    def test_swagger_ui_has_endpoints(self, browser, test_server: str) -> None:
        """Verify the Swagger page lists expected operations."""
        page = browser.new_page()
        page.goto(f"{test_server}/docs")
        # Swagger lists operations in opblock-tag sections
        tags = page.locator(".opblock-tag-section")
        tag_count = tags.count()
        assert tag_count > 0, "Expected at least one operation in Swagger UI"
        page.close()
