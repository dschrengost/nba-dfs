import { test, expect } from '@playwright/test';

test.describe('Optimizer Settings UI', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/optimizer');
  });

  test('shows sliders for Sigma and Drop with tooltips', async ({ page }) => {
    // Sliders present
    await expect(page.getByTestId('sigma-slider')).toBeVisible();
    await expect(page.getByTestId('drop-slider')).toBeVisible();

    // Sigma tooltip
    const sigmaLabel = page.getByText('Sigma (0–0.25)', { exact: true });
    await sigmaLabel.hover();
    await expect(page.getByText('Randomness applied to projections.', { exact: false })).toBeVisible();

    // Drop tooltip
    const dropLabel = page.getByText('Drop intensity (0–0.5)', { exact: true });
    await dropLabel.hover();
    await expect(page.getByText('Prunes low-projection players to speed up search.', { exact: false })).toBeVisible();
  });
});

