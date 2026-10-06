import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Navigate to morning brief
        print('Navigating to Morning Brief...')
        await page.goto('http://localhost:5173/pro', wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Take screenshot
        await page.screenshot(path='morning_brief.png', full_page=True)
        print('Morning Brief screenshot saved')
        
        # Get page content
        content = await page.content()
        print(f'Page length: {len(content)} chars')
        
        # Get text content
        text = await page.inner_text('body')
        print('=== PAGE TEXT (first 5000 chars) ===')
        print(text[:5000])
        
        await browser.close()

asyncio.run(main())