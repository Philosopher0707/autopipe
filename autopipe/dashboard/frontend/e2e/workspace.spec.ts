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

test.describe('Workspace', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('loads workspace panels', async ({ page }) => {
    await page.goto('/workspace')
    await expect(page.getByRole('heading', { name: 'Workspace' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Metric Over Time' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Key Metrics' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Metric Correlation' })).toBeVisible()
  })
})
