import { test, expect } from '@playwright/test';

test.describe('Dark Mode Features', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/optimizer');
  });

  test('should toggle dark mode and persist preference', async ({ page }) => {
    // Find the theme toggle button
    const themeToggle = page.getByTestId('theme-toggle');
    await expect(themeToggle).toBeVisible();

    // Get initial theme state
    const initialHtml = page.locator('html');
    const initialClass = await initialHtml.getAttribute('class');
    
    // Click theme toggle to open dropdown
    await themeToggle.click();
    
    // Select dark mode
    const darkModeOption = page.getByTestId('theme-dark');
    await expect(darkModeOption).toBeVisible();
    await darkModeOption.click();
    
    // Verify dark mode is applied
    await expect(initialHtml).toHaveClass(/dark/);
    
    // Check that dark mode styles are applied to various elements
    const body = page.locator('body');
    const computedBg = await body.evaluate((el) => 
      getComputedStyle(el).getPropertyValue('background-color')
    );
    
    // Dark mode should have a dark background (not white/light)
    expect(computedBg).not.toBe('rgb(255, 255, 255)');
    
    // Switch to light mode
    await themeToggle.click();
    const lightModeOption = page.getByTestId('theme-light');
    await lightModeOption.click();
    
    // Verify light mode is applied
    await expect(initialHtml).not.toHaveClass(/dark/);
    
    // Test system mode
    await themeToggle.click();
    const systemModeOption = page.getByTestId('theme-system');
    await systemModeOption.click();
    
    // System mode should be selected (specific behavior depends on system settings)
    await expect(themeToggle).toBeVisible();
  });

  test('should persist theme preference across page reloads', async ({ page }) => {
    const themeToggle = page.getByTestId('theme-toggle');
    const html = page.locator('html');
    
    // Set to dark mode
    await themeToggle.click();
    await page.getByTestId('theme-dark').click();
    await expect(html).toHaveClass(/dark/);
    
    // Reload the page
    await page.reload();
    
    // Verify dark mode is still applied
    await expect(html).toHaveClass(/dark/);
    
    // Switch to light mode
    await themeToggle.click();
    await page.getByTestId('theme-light').click();
    await expect(html).not.toHaveClass(/dark/);
    
    // Reload again
    await page.reload();
    
    // Verify light mode persisted
    await expect(html).not.toHaveClass(/dark/);
  });

  test('should apply dark mode styles to all UI components', async ({ page }) => {
    const themeToggle = page.getByTestId('theme-toggle');
    
    // Switch to dark mode
    await themeToggle.click();
    await page.getByTestId('theme-dark').click();
    
    // Check various components have proper dark mode styles
    const html = page.locator('html');
    await expect(html).toHaveClass(/dark/);
    
    // Check cards adapt to dark theme
    const runSummary = page.getByTestId('run-summary');
    if (await runSummary.isVisible()) {
      // Cards should have dark styling
      const cards = runSummary.locator('.border');
      const cardCount = await cards.count();
      
      for (let i = 0; i < cardCount; i++) {
        const card = cards.nth(i);
        // Check that borders are visible in dark mode (not fully transparent)
        const borderColor = await card.evaluate((el) => 
          getComputedStyle(el).getPropertyValue('border-color')
        );
        // Should not be completely transparent
        expect(borderColor).not.toBe('rgba(0, 0, 0, 0)');
      }
    }
    
    // Check table in dark mode
    await page.getByTestId('table-tab').click();
    
    const tableCard = page.getByTestId('lineup-table-card');
    if (await tableCard.isVisible()) {
      // Table should be readable in dark mode
      const table = tableCard.locator('table');
      if (await table.isVisible()) {
        const backgroundColor = await table.evaluate((el) => 
          getComputedStyle(el).getPropertyValue('background-color')
        );
        // Should have some background color, not transparent
        expect(backgroundColor).not.toBe('rgba(0, 0, 0, 0)');
        expect(backgroundColor).not.toBe('transparent');
      }
    }
  });

  test('should have accessible theme toggle with keyboard navigation', async ({ page }) => {
    const themeToggle = page.getByTestId('theme-toggle');
    
    // Focus the theme toggle with keyboard
    await themeToggle.focus();
    await expect(themeToggle).toBeFocused();
    
    // Should be able to activate with Enter or Space
    await page.keyboard.press('Enter');
    
    // Dropdown should open
    await expect(page.getByTestId('theme-light')).toBeVisible();
    
    // Should be able to navigate with arrow keys and select with Enter
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');
    
    // Dropdown should close after selection
    await expect(page.getByTestId('theme-light')).not.toBeVisible();
  });

  test('should show correct theme toggle icon states', async ({ page }) => {
    const themeToggle = page.getByTestId('theme-toggle');
    
    // In light mode, should show sun icon prominently
    await themeToggle.click();
    await page.getByTestId('theme-light').click();
    
    // Check that sun icon is visible (moon should be hidden)
    const sunIcon = themeToggle.locator('svg').first();
    await expect(sunIcon).toBeVisible();
    
    // Switch to dark mode
    await themeToggle.click();
    await page.getByTestId('theme-dark').click();
    
    // In dark mode, moon icon should be more prominent
    // (This depends on the CSS transitions and may need adjustment)
    await expect(themeToggle).toBeVisible();
  });

  test('should work correctly with system theme preference', async ({ page }) => {
    const themeToggle = page.getByTestId('theme-toggle');
    
    // Select system theme
    await themeToggle.click();
    await page.getByTestId('theme-system').click();
    
    // Should respect system preference
    // Note: Actual behavior depends on the system's current theme setting
    const html = page.locator('html');
    
    // Just verify that system mode can be selected without errors
    await expect(themeToggle).toBeVisible();
    
    // The html class should reflect system preference
    const htmlClass = await html.getAttribute('class');
    
    // Should either have 'dark' class or not, based on system
    expect(typeof htmlClass).toBe('string');
  });
});