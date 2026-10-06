import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Navigate to workflow
        print('Navigating to Workflow...')
        await page.goto('http://localhost:5173/workflow', wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Take screenshot
        await page.screenshot(path='workflow.png', full_page=True)
        print('Workflow screenshot saved')
        
        # Get text content
        text = await page.inner_text('body')
        safe_text = text.encode('ascii', 'replace').decode('ascii')
        print('=== WORKFLOW PAGE TEXT (first 5000 chars) ===')
        print(safe_text[:5000])
        
        await browser.close()

asyncio.run(main())