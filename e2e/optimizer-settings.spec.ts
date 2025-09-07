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

  test('advanced settings collapsible toggles content', async ({ page }) => {
    // Collapsible trigger should be visible
    const advToggle = page.getByRole('button', { name: /advanced settings/i });
    // Our trigger is an icon button without an accessible name, so fall back to the label nearby
    const advLabel = page.getByText('Advanced Settings', { exact: true });
    await expect(advLabel).toBeVisible();

    // Click the button next to label
    const btn = advLabel.locator('xpath=following-sibling::*//button').first();
    await btn.click();

    // Expect advanced fields to appear
    await expect(page.getByText('Ownership penalty', { exact: false })).toBeVisible();
  });
});
