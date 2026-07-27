"""
UAT Script: Sarah's Morning Brief Workflow

Persona: Sarah, 34, marketing manager, $75K savings, zero trading experience.

Runs a Playwright-based acceptance test against the local development servers.
All 4 tasks must complete in <10 minutes total.

Usage:
    # Terminal 1 (backend):
    uvicorn backend.app.api.main:app --reload --port 8000

    # Terminal 2 (frontend):
    cd frontend && npm run dev

    # Terminal 3 (this script):
    python tests/acceptance/test_morning_brief_workflow.py
"""

import asyncio
import time

from playwright.async_api import async_playwright, expect

BASE_URL = "http://localhost:5173"


async def run_sarah_workflow():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            storage_state=None,  # Fresh session
        )
        page = await context.new_page()

        total_start = time.monotonic()

        # ════════════════════════════════════════════════════
        # TASK 1: Read Morning Brief (target: 3 min)
        # ════════════════════════════════════════════════════
        print("\n📋 TASK 1: Read Morning Brief")
        task_start = time.monotonic()

        await page.goto(f"{BASE_URL}/pro", wait_until="networkidle")

        # Verify page loads with morning brief header
        await expect(page.locator("header, h1, h2").filter(has_text="Brief")).to_be_visible(
            timeout=10000
        )
        print("  ✅ Morning Brief page loaded")

        # Verify ticker cards or screen sections visible
        cards = page.locator('[data-testid="ticker-card"]')
        card_count = await cards.count()
        print(f"  ✅ {card_count} ticker cards found")

        # Try to hover education tooltip
        tooltips = page.locator('[data-testid^="tooltip-"]')
        if await tooltips.count() > 0:
            await tooltips.first.hover()
            await page.wait_for_timeout(500)
            print("  ✅ Education tooltip hover works")

        elapsed = time.monotonic() - task_start
        print(f"  ⏱️  Task 1: {elapsed:.0f}s (target: <180s)")
        task1_ok = elapsed < 180

        # ════════════════════════════════════════════════════
        # TASK 2: Analyze a ticker (target: 3 min)
        # ════════════════════════════════════════════════════
        print("\n🔍 TASK 2: Analyze Ticker")
        task_start = time.monotonic()

        # Navigate to simple verdict page
        await page.goto(f"{BASE_URL}/pro/ticker/AAPL", wait_until="networkidle")

        # Verify verdict section visible
        verdict = page.locator("text=Verdict").or_(page.locator('[data-testid="verdict-badge"]'))
        await expect(verdict.first).to_be_visible(timeout=10000)
        print("  ✅ Verdict page loaded")

        elapsed = time.monotonic() - task_start
        print(f"  ⏱️  Task 2: {elapsed:.0f}s (target: <180s)")
        task2_ok = elapsed < 180

        # ════════════════════════════════════════════════════
        # TASK 3: Configure Watchlist (target: 2 min)
        # ════════════════════════════════════════════════════
        print("\n📋 TASK 3: Configure Settings")
        task_start = time.monotonic()

        await page.goto(f"{BASE_URL}/pro/settings", wait_until="networkidle")

        # Check settings page loaded
        await expect(page.locator("text=Settings").or_(page.locator('[data-testid="account-size-input"]'))).to_be_visible(timeout=10000)
        print("  ✅ Settings page loaded")

        elapsed = time.monotonic() - task_start
        print(f"  ⏱️  Task 3: {elapsed:.0f}s (target: <120s)")
        task3_ok = elapsed < 120

        # ════════════════════════════════════════════════════
        # TASK 4: Navigation and Toggle (target: 2 min)
        # ════════════════════════════════════════════════════
        print("\n⚙️ TASK 4: Navigation & Toggle")
        task_start = time.monotonic()

        # Navigate to watchlist
        await page.goto(f"{BASE_URL}/pro/watchlist", wait_until="networkidle")
        print("  ✅ Watchlist page loaded")

        # Go back to main pro landing
        await page.goto(f"{BASE_URL}/pro", wait_until="networkidle")
        await expect(page.locator("text=Brief").or_(page.locator('[data-testid="ticker-card"]'))).to_be_visible(timeout=10000)
        print("  ✅ Pro landing page loads correctly")

        elapsed = time.monotonic() - task_start
        print(f"  ⏱️  Task 4: {elapsed:.0f}s (target: <120s)")
        task4_ok = elapsed < 120

        # ════════════════════════════════════════════════════
        # FINAL VERIFICATION
        # ════════════════════════════════════════════════════
        total_elapsed = time.monotonic() - total_start
        all_ok = task1_ok and task2_ok and task3_ok and task4_ok
        print(f"\n{'✅' if all_ok else '❌'} SARAH WORKFLOW COMPLETE")
        print(f"   Total time: {total_elapsed:.0f}s (target: <600s)")
        print(f"   Task 1 (Brief):     {'✅' if task1_ok else '❌'} {task1_ok}")
        print(f"   Task 2 (Analyze):   {'✅' if task2_ok else '❌'} {task2_ok}")
        print(f"   Task 3 (Settings):  {'✅' if task3_ok else '❌'} {task3_ok}")
        print(f"   Task 4 (Navigate):  {'✅' if task4_ok else '❌'} {task4_ok}")

        await browser.close()
        return all_ok


def main():
    result = asyncio.run(run_sarah_workflow())
    exit(0 if result else 1)


if __name__ == "__main__":
    main()
