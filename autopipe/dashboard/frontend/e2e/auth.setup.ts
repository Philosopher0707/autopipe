import { test as base, expect, Page } from '@playwright/test'

export async function login(page: Page) {
  await page.goto('/login')
  await page.fill('#username', 'admin')
  await page.fill('#password', 'admin123')
  await page.click('button[type="submit"]')
  await expect(page).toHaveURL('/')
}

export const test = base.extend<{
  authenticatedPage: Page
}>({
  authenticatedPage: async ({ page }, use) => {
    await login(page)
    await use(page)
  },
})

export { expect }
