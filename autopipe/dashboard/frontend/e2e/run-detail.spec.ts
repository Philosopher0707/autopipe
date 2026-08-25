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

test.describe('Run Detail', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('opens run detail and switches tabs', async ({ page }) => {
    await page.goto('/runs')
    await page.waitForSelector('table tbody tr')

    // click first run row heading
    const firstRun = page.locator('table tbody tr').first().getByRole('heading')
    await firstRun.click()
    await page.waitForURL(/\/runs\//, { timeout: 10000 })

    await expect(page.locator('button').filter({ hasText: 'Charts' })).toBeVisible()
    await expect(page.locator('button').filter({ hasText: 'Overview' })).toBeVisible()
    await expect(page.locator('button').filter({ hasText: 'Logs' })).toBeVisible()
    await expect(page.locator('button').filter({ hasText: 'Files' })).toBeVisible()
    await expect(page.locator('button').filter({ hasText: 'Artifacts' })).toBeVisible()

    // Overview tab
    await page.locator('button').filter({ hasText: 'Overview' }).click()
    await expect(page.getByRole('heading', { name: 'Steps' })).toBeVisible()

    // Logs tab
    await page.locator('button').filter({ hasText: 'Logs' }).click()
    await expect(page.getByText(/No logs available/)).toBeVisible()

    // Files tab
    await page.locator('button').filter({ hasText: 'Files' }).click()
    await expect(page.getByText('No files attached')).toBeVisible()

    // Artifacts tab
    await page.locator('button').filter({ hasText: 'Artifacts' }).click()
    await expect(page.getByText('No chart artifacts')).toBeVisible()
  })

  test('QueryBar filters steps in Overview tab', async ({ page }) => {
    await page.goto('/runs')
    await page.waitForSelector('table tbody tr')

    // open a success run
    const rows = page.locator('table tbody tr')
    for (let i = 0; i < await rows.count(); i++) {
      const status = await rows.nth(i).locator('td').nth(3).textContent()
      if (status?.includes('success')) {
        await rows.nth(i).getByRole('heading').click()
        break
      }
    }

    await page.waitForURL(/\/runs\//, { timeout: 10000 })
    await page.locator('button').filter({ hasText: 'Overview' }).click()
    await expect(page.getByRole('heading', { name: 'Steps' })).toBeVisible()

    // type in filter
    await page.locator('input[placeholder="Filter steps..."]').fill('train')
    await expect(page.getByText('train').first()).toBeVisible()
  })
})
