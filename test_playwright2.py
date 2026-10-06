import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Navigate to screener
        print('Navigating to Screener...')
        await page.goto('http://localhost:5173/screener', wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Take screenshot
        await page.screenshot(path='screener.png', full_page=True)
        print('Screener screenshot saved')
        
        # Get text content
        text = await page.inner_text('body')
        safe_text = text.encode('ascii', 'replace').decode('ascii')
        print('=== SCREENER PAGE TEXT (first 5000 chars) ===')
        print(safe_text[:5000])
        
        await browser.close()

asyncio.run(main())