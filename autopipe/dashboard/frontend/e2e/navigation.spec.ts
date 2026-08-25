import { test, expect } from '@playwright/test'

async function login(page: any) {
  const res = await page.request.post('http://localhost:8765/api/v1/auth/login', {
    data: { username: 'admin', password: 'admin123' },
  })
  const { access_token } = await res.json()
  await page.goto('/login')
  await page.evaluate((token: string) => {
    localStorage.setItem('auth_token', token)
    localStorage.setItem('auth-storage', JSON.stringify({ state: { token, isAuthenticated: true, user: null }, version: 0 }))
  }, access_token)
  await page.goto('/')
  await page.waitForSelector('aside nav', { timeout: 15000 })
}

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('sidebar shows all nav items', async ({ page }) => {
    const aside = page.locator('aside')
    await expect(aside.getByText('Dashboard')).toBeVisible()
    await expect(aside.getByText('Workspace')).toBeVisible()
    await expect(aside.getByText('Pipelines')).toBeVisible()
    await expect(aside.getByText('Runs')).toBeVisible()
    await expect(aside.getByText('Experiments')).toBeVisible()
    await expect(aside.getByText('Model Registry')).toBeVisible()
    await expect(aside.getByText('Drift Monitor')).toBeVisible()
    await expect(aside.getByText('Explainability')).toBeVisible()
    await expect(aside.getByText('AutoML')).toBeVisible()
    await expect(aside.getByText('Features')).toBeVisible()
    await expect(aside.getByText('Projects')).toBeVisible()
    await expect(aside.getByText('Settings')).toBeVisible()
    await expect(aside.getByText('Team')).toBeVisible()
    await expect(aside.getByText('Profile')).toBeVisible()
  })

  test('sidebar collapse toggle works', async ({ page }) => {
    const toggle = page.locator('aside').locator('button').first()
    await toggle.click()
    await expect(page.locator('aside')).toHaveClass(/w-14/)
    await toggle.click()
    await expect(page.locator('aside')).toHaveClass(/w-64/)
  })

  test('Projects page loads with grid and table views', async ({ page }) => {
    await page.goto('/projects')
    await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible()
    await expect(page.getByText('Image Classification')).toBeVisible()

    // switch to table view (second button in toggle group)
    await page.locator('div.flex.border.rounded-lg.overflow-hidden button').nth(1).click()
    await expect(page.locator('table')).toBeVisible()

    // switch back to grid
    await page.locator('div.flex.border.rounded-lg.overflow-hidden button').nth(0).click()
    await expect(page.getByText('Image Classification')).toBeVisible()
  })

  test('Profile page loads with tabs', async ({ page }) => {
    await page.goto('/profile')
    await expect(page.getByRole('heading', { name: 'Profile' })).toBeVisible()

    await expect(page.locator('button').filter({ hasText: 'Overview' })).toBeVisible()
    await expect(page.locator('button').filter({ hasText: 'Settings' })).toBeVisible()
    await expect(page.locator('button').filter({ hasText: 'API Keys' })).toBeVisible()

    await page.locator('button').filter({ hasText: 'Settings' }).click()
    await expect(page.getByText('Full Name')).toBeVisible()

    await page.locator('button').filter({ hasText: 'API Keys' }).click()
    await expect(page.getByText('Production')).toBeVisible()
  })

  test('breadcrumb renders on nested pages', async ({ page }) => {
    await page.goto('/runs')
    const header = page.locator('header')
    await expect(header.getByText('Home')).toBeVisible()
    await expect(header.locator('span').filter({ hasText: 'Runs' })).toBeVisible()
  })
})
