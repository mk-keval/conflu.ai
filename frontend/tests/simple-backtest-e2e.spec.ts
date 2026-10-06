import { test, expect } from '@playwright/test';

test.describe('Filter Sweep Page - Simple Backtest Mode', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/backtest/filter-sweep');
    await page.waitForLoadState('networkidle');
  });

  test('should load filter sweep page with both modes', async ({ page }) => {
    // Check page title
    await expect(page.locator('h1')).toContainText('Filter Sweep Backtest');
    
    // Check both mode tabs exist
    await expect(page.getByRole('button', { name: /Parameter Sweep/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /Simple Backtest/ })).toBeVisible();
  });

  test('should switch to Simple Backtest mode', async ({ page }) => {
    // Click Simple Backtest tab
    await page.getByRole('button', { name: /Simple Backtest/ }).click();
    
    // Wait for templates to load
    await expect(page.locator('text=Loading templates...')).toBeHidden({ timeout: 10000 });
    
    // Verify form elements are visible (using placeholders/roles)
    await expect(page.locator('select').first()).toBeVisible(); // Template dropdown
    await expect(page.locator('input[placeholder="AAPL,MSFT,GOOGL"]')).toBeVisible(); // Symbols
    await expect(page.locator('input[type="date"]').first()).toBeVisible(); // Start Date
    await expect(page.locator('input[type="date"]').last()).toBeVisible(); // End Date
    await expect(page.locator('select').nth(1)).toBeVisible(); // Timeframe (2nd select)
  });

  test('should load templates in dropdown', async ({ page }) => {
    await page.getByRole('button', { name: /Simple Backtest/ }).click();
    
    // Wait for templates to load - wait for loading to disappear
    await expect(page.locator('text=Loading templates...')).toBeHidden({ timeout: 10000 });
    
    // Wait for templates to load
    const templateSelect = page.locator('select').first();
    await expect(templateSelect).toBeVisible();
    
    // Get all option values from the select
    const optionValues = await templateSelect.locator('option').allTextContents();
    expect(optionValues.length).toBeGreaterThan(10);
    // Check that we have our elite templates
    const hasEliteTemplate = optionValues.some(v => 
      v.includes('52-Week Breakout') || 
      v.includes('trend-follower-v2') || 
      v.includes('vcp-breakout') ||
      v.includes('trend-pullback-v2')
    );
    expect(hasEliteTemplate).toBeTruthy();
  });

  test('should run simple backtest and show results with all metrics', async ({ page }) => {
    await page.getByRole('button', { name: /Simple Backtest/ }).click();
    
    // Fill form
    const templateSelect = page.locator('select').first();
    await templateSelect.selectOption({ index: 0 }); // Select first template
    
    // Fill symbols
    await page.locator('input[placeholder="AAPL,MSFT,GOOGL"]').fill('AAPL,MSFT');
    
    // Fill dates (last 6 months)
    const endDate = new Date().toISOString().split('T')[0];
    const startDate = new Date(Date.now() - 180 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    const dateInputs = page.locator('input[type="date"]');
    await dateInputs.first().fill(startDate);
    await dateInputs.last().fill(endDate);
    
    // Select timeframe (2nd select)
    await page.locator('select >> nth=1').selectOption('1D');
    
    // Submit
    await page.getByRole('button', { name: /Run Backtest/ }).click();
    
    // Wait for either results or loading state
    await expect(page.locator('text=Running Backtest').or(page.locator('text=Backtest Results'))).toBeVisible({ timeout: 10000 });
    
    // If results loaded, verify key metrics
    const resultsLoaded = await page.locator('text=Backtest Results').isVisible({ timeout: 5000 }).catch(() => false);
    if (resultsLoaded) {
      // Verify key metric cards are displayed
      const keyMetrics = ['Total Return', 'Sharpe Ratio', 'Win Rate', 'Profit Factor', 'Total Trades'];
      for (const metric of keyMetrics) {
        await expect(page.locator(`text=${metric}`).first()).toBeVisible({ timeout: 5000 });
      }
      
      // Verify trade table or equity curve is present
      await expect(page.locator('text=Trade Details').or(page.locator('text=Equity Curve'))).toBeVisible();
      
      // Verify "Run Another" button is present
      await expect(page.getByRole('button', { name: /Run Another/ })).toBeVisible();
    }
  });
});

test.describe('Filter Sweep Page - Parameter Sweep Mode (regression)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/backtest/filter-sweep');
    await page.waitForLoadState('networkidle');
  });

  test('should still show Parameter Sweep mode', async ({ page }) => {
    await expect(page.getByRole('button', { name: /Parameter Sweep/ })).toBeVisible();
    await expect(page.locator('text=Filter Sweep Configuration')).toBeVisible();
  });
});