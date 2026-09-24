import asyncio
from playwright.async_api import async_playwright

def safe_print(text):
    """Safe print for Windows console"""
    if text:
        safe_text = text.encode('ascii', 'replace').decode('ascii')
        print(safe_text)

async def explore():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        page.set_default_timeout(30000)
        
        safe_print('=== EXPLORING KEY PAGES AS BEGINNER ===')
        
        # Helper to navigate and capture
        async def visit_and_capture(url, name):
            safe_print(f'\n--- Visiting {name} ---')
            await page.goto(url, wait_until='networkidle')
            await page.wait_for_timeout(2000)
            await page.screenshot(path=f'{name}.png')
            title = await page.title()
            safe_print(f'   Title: {title}')
            text = await page.locator('body').text_content()
            if text:
                safe_print(f'   Content preview: {text[:300]}')
            return text
        
        # Start at home
        await page.goto('http://localhost:5173', wait_until='networkidle')
        await page.wait_for_timeout(2000)
        
        # 1. Morning Brief
        safe_print('\n=== 1. MORNING BRIEF ===')
        morning_link = page.locator('text=Morning Brief').first
        if await morning_link.count() > 0:
            await morning_link.click()
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(3000)
            await page.screenshot(path='morning_brief.png')
            text = await page.locator('body').text_content()
            if text:
                safe_print(f'Content preview: {text[:500]}')
        
        # 2. Screener
        safe_print('\n=== 2. SCREENER ===')
        screener_link = page.locator('text=Screener').first
        if await screener_link.count() > 0:
            await screener_link.click()
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(3000)
            await page.screenshot(path='screener.png')
            text = await page.locator('body').text_content()
            if text:
                safe_print(f'Content preview: {text[:500]}')
        
        # 3. Ticker Analysis
        safe_print('\n=== 3. TICKER ANALYSIS ===')
        ticker_link = page.locator('text=Ticker Analysis').first
        if await ticker_link.count() > 0:
            await ticker_link.click()
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(3000)
            await page.screenshot(path='ticker_analysis.png')
            text = await page.locator('body').text_content()
            if text:
                safe_print(f'Content preview: {text[:500]}')
        
        # 4. Swing Desk
        safe_print('\n=== 4. SWING DESK ===')
        desk_link = page.locator('text=Swing Desk').first
        if await desk_link.count() > 0:
            await desk_link.click()
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(3000)
            await page.screenshot(path='swing_desk.png')
            text = await page.locator('body').text_content()
            if text:
                safe_print(f'Content preview: {text[:500]}')
        
        # 5. Learn / Education
        safe_print('\n=== 5. LEARN / EDUCATION ===')
        learn_link = page.locator('text=Learn').first
        if await learn_link.count() > 0:
            await learn_link.click()
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(3000)
            await page.screenshot(path='learn.png')
            text = await page.locator('body').text_content()
            if text:
                safe_print(f'Content preview: {text[:500]}')
        
        # 6. Charts
        safe_print('\n=== 6. CHARTS ===')
        charts_link = page.locator('text=Charts').first
        if await charts_link.count() > 0:
            await charts_link.click()
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(3000)
            await page.screenshot(path='charts.png')
            text = await page.locator('body').text_content()
            if text:
                safe_print(f'Content preview: {text[:500]}')
        
        # 7. Sector Rotation
        safe_print('\n=== 7. SECTOR ROTATION ===')
        sector_link = page.locator('text=Sector Rotation').first
        if await sector_link.count() > 0:
            await sector_link.click()
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(3000)
            await page.screenshot(path='sector_rotation.png')
            text = await page.locator('body').text_content()
            if text:
                safe_print(f'Content preview: {text[:500]}')
        
        # 8. Try analyzing a specific ticker (AAPL)
        safe_print('\n=== 8. ANALYZING AAPL ===')
        await page.goto('http://localhost:5173/ticker?symbol=AAPL', wait_until='networkidle')
        await page.wait_for_timeout(5000)
        await page.screenshot(path='aapl_analysis.png')
        text = await page.locator('body').text_content()
        if text:
            safe_print(f'Content preview: {text[:500]}')
        
        # 9. Try MSFT
        safe_print('\n=== 9. ANALYZING MSFT ===')
        await page.goto('http://localhost:5173/ticker?symbol=MSFT', wait_until='networkidle')
        await page.wait_for_timeout(5000)
        await page.screenshot(path='msft_analysis.png')
        text = await page.locator('body').text_content()
        if text:
            safe_print(f'Content preview: {text[:500]}')
        
        await browser.close()
        safe_print('\n=== EXPLORATION COMPLETE ===')

asyncio.run(explore())