import asyncio
from playwright.async_api import async_playwright

async def explore():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        page.set_default_timeout(30000)
        
        print('=== STARTING EXPLORATION AS WORKING PROFESSIONAL BEGINNER ===')
        
        # 1. Start at home
        print('\n1. Navigating to home page...')
        await page.goto('http://localhost:5173', wait_until='networkidle')
        await page.screenshot(path='1_home.png')
        print('   Title:', await page.title())
        
        # Look for navigation
        print('\n2. Looking for navigation elements...')
        nav_items = await page.locator('nav, [role=navigation], header, .sidebar, aside').all()
        print(f'   Found {len(nav_items)} nav containers')
        
        # Get all clickable links/buttons
        links = await page.locator('a, button[href], [role=button], [data-testid]').all()
        print(f'   Found {len(links)} interactive elements')
        
        # Get visible text for navigation
        text_content = await page.locator('body').text_content()
        if text_content:
            print(f'   Page text sample: {text_content[:500]}')
        else:
            print('   Page text sample: (empty)')
        
        # 3. Look for Morning Brief, Screener, etc.
        print('\n3. Looking for key pages...')
        key_terms = ['Morning', 'Brief', 'Screener', 'Swing', 'Ticker', 'Analysis', 'Chart', 'Desk', 'Portfolio', 'Learn', 'Education']
        for term in key_terms:
            elements = await page.locator(f'text={term}').all()
            if elements:
                print(f'   [FOUND] "{term}" ({len(elements)} elements)')
            else:
                print(f'   [MISSING] "{term}"')
        
        await browser.close()

asyncio.run(explore())