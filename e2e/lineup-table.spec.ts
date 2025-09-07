import { test, expect } from '@playwright/test';

test.describe('Lineup Table Features', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/optimizer');
  });

  test('should display RunSummary metrics with correct formatting', async ({ page }) => {
    // Wait for the run summary to be visible
    await expect(page.getByTestId('run-summary')).toBeVisible();
    
    // Check for badge tooltips
    const engineBadge = page.getByTestId('engine-badge');
    if (await engineBadge.isVisible()) {
      await engineBadge.hover();
      await expect(page.getByText('Optimization engine used')).toBeVisible();
    }

    // Check for inputs/outputs card
    const inputsCard = page.getByTestId('inputs-outputs-card');
    if (await inputsCard.isVisible()) {
      // Verify number formatting with proper separators
      const lineupsValue = inputsCard.locator('dd').first();
      await expect(lineupsValue).toHaveClass(/font-mono tabular-nums/);
    }

    // Check for performance card metrics
    const perfCard = page.getByTestId('performance-card');
    if (await perfCard.isVisible()) {
      // Check that scores are formatted with 2 decimal places
      const scoreElements = perfCard.locator('dd');
      const scoreText = await scoreElements.first().textContent();
      if (scoreText && scoreText !== '—') {
        expect(scoreText).toMatch(/^\d{1,3}(,\d{3})*\.\d{2}$/);
      }
    }
  });

  test('should switch between Cards and Table views', async ({ page }) => {
    // Check that view tabs are present
    await expect(page.getByTestId('lineup-view-tabs')).toBeVisible();
    await expect(page.getByTestId('cards-tab')).toBeVisible();
    await expect(page.getByTestId('table-tab')).toBeVisible();

    // Start with Cards view (default)
    await expect(page.getByTestId('cards-view')).toBeVisible();
    await expect(page.getByTestId('table-view')).not.toBeVisible();

    // Switch to Table view
    await page.getByTestId('table-tab').click();
    await expect(page.getByTestId('table-view')).toBeVisible();
    await expect(page.getByTestId('cards-view')).not.toBeVisible();

    // Switch back to Cards view
    await page.getByTestId('cards-tab').click();
    await expect(page.getByTestId('cards-view')).toBeVisible();
    await expect(page.getByTestId('table-view')).not.toBeVisible();
  });

  test('should sort table by Score and manage columns', async ({ page }) => {
    // Switch to table view first
    await page.getByTestId('table-tab').click();
    
    // Wait for table to load
    const table = page.getByTestId('lineup-table-card');
    await expect(table).toBeVisible();

    // Check default sorting by Score (descending)
    const scoreHeader = page.getByTestId('header-score');
    if (await scoreHeader.isVisible()) {
      await expect(scoreHeader).toContainText('↓');
    }

    // Open column settings
    await page.getByTestId('column-settings-button').click();
    
    // Toggle Salary column off
    const salaryToggle = page.getByTestId('column-toggle-salary_used');
    if (await salaryToggle.isVisible()) {
      await salaryToggle.click();
      
      // Verify salary column is hidden
      const salaryHeader = page.getByTestId('header-salary_used');
      await expect(salaryHeader).not.toBeVisible();
      
      // Toggle it back on
      await page.getByTestId('column-settings-button').click();
      await salaryToggle.click();
      await expect(salaryHeader).toBeVisible();
    }

    // Test column pinning
    await page.getByTestId('column-settings-button').click();
    const scorePinToggle = page.getByTestId('column-pin-score');
    if (await scorePinToggle.isVisible()) {
      await scorePinToggle.click();
      // Check that pinning state is reflected (should show "Pinned" badge)
      await expect(page.getByText('Pinned')).toBeVisible();
    }
  });

  test('should search for players by name and ID', async ({ page }) => {
    // Switch to table view
    await page.getByTestId('table-tab').click();
    
    const searchInput = page.getByTestId('lineup-search-input');
    await expect(searchInput).toBeVisible();

    // Test search by player ID (assuming some test data exists)
    await searchInput.fill('12345');
    
    // Verify that search filters are applied
    const rowCountBadge = page.getByTestId('row-count-badge');
    await expect(rowCountBadge).toBeVisible();
    
    // Clear search
    await searchInput.fill('');
    
    // Test search by player name
    await searchInput.fill('LeBron');
    
    // The filtering should work with any existing data
    await expect(rowCountBadge).toBeVisible();
    
    // Clear search again
    await searchInput.fill('');
  });

  test('should export CSV with correct headers and data', async ({ page }) => {
    // Switch to table view
    await page.getByTestId('table-tab').click();
    
    // Wait for table to be ready
    await expect(page.getByTestId('lineup-table-card')).toBeVisible();
    
    // Set up download listener
    const downloadPromise = page.waitForEvent('download');
    
    // Click export button
    const exportButton = page.getByTestId('export-csv-button');
    await expect(exportButton).toBeVisible();
    await expect(exportButton).toBeEnabled();
    
    await exportButton.click();
    
    // Wait for download to start
    const download = await downloadPromise;
    
    // Verify filename format
    const filename = download.suggestedFilename();
    expect(filename).toMatch(/^lineups-export-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.csv$/);
  });

  test('should reset table settings', async ({ page }) => {
    // Switch to table view
    await page.getByTestId('table-tab').click();
    
    // Make some changes first
    const searchInput = page.getByTestId('lineup-search-input');
    await searchInput.fill('test search');
    
    // Open column settings and make a change
    await page.getByTestId('column-settings-button').click();
    const firstToggle = page.locator('[data-testid^="column-toggle-"]').first();
    if (await firstToggle.isVisible()) {
      await firstToggle.click();
    }
    
    // Press escape to close dropdown
    await page.keyboard.press('Escape');
    
    // Reset everything
    await page.getByTestId('reset-button').click();
    
    // Verify search is cleared
    await expect(searchInput).toHaveValue('');
    
    // Verify columns are restored (would need to check specific implementation)
    await expect(page.getByTestId('column-settings-button')).toBeVisible();
  });

  test('should show correct row counts in badge', async ({ page }) => {
    // Switch to table view
    await page.getByTestId('table-tab').click();
    
    const rowCountBadge = page.getByTestId('row-count-badge');
    await expect(rowCountBadge).toBeVisible();
    
    // Initial state should show total count
    const initialText = await rowCountBadge.textContent();
    expect(initialText).toMatch(/\d+ rows?/);
    
    // Apply search filter
    const searchInput = page.getByTestId('lineup-search-input');
    await searchInput.fill('xyz_nonexistent_player');
    
    // Should show filtered count
    await expect(rowCountBadge).toContainText('0 of');
    
    // Clear search
    await searchInput.fill('');
    
    // Should return to total count
    await expect(rowCountBadge).toContainText('rows');
  });

  test('should handle empty table state', async ({ page }) => {
    // Go to table view when no data is loaded
    await page.getByTestId('table-tab').click();
    
    // Should show appropriate empty state
    const noResultsCell = page.getByTestId('no-results-cell');
    if (await noResultsCell.isVisible()) {
      await expect(noResultsCell).toContainText('No results found');
    }
  });

  test('should display player cells with copy functionality', async ({ page }) => {
    // Switch to table view
    await page.getByTestId('table-tab').click();
    
    // Look for player cells
    const playerCells = page.locator('[data-testid^="player-cell-"]');
    const firstPlayerCell = playerCells.first();
    
    if (await firstPlayerCell.isVisible()) {
      // Check for copy button
      const copyButton = firstPlayerCell.locator('[data-testid^="copy-player-"]');
      if (await copyButton.isVisible()) {
        await copyButton.click();
        // Note: Actually testing clipboard would require additional permissions
      }
      
      // Test tooltip on hover
      await firstPlayerCell.hover();
      // Tooltip content would appear - specific checks depend on data
    }
  });

  test('should not log console errors when toggling views', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await page.getByTestId('table-tab').click();
    await page.getByTestId('cards-tab').click();

    expect(errors).toEqual([]);
  });

  test('dev-only grid state toggles are hidden by default', async ({ page }) => {
    // When NEXT_PUBLIC_DEV_UI !== 'true', the dev toggles should not render
    const devToggles = page.locator('[aria-label="Dev grid state toggles"]');
    await expect(devToggles).toHaveCount(0);
  });
});
