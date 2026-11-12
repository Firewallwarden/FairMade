import { test, expect } from './fixtures'
import { signIn, field, posted } from './helpers'

test('served website identifies the checkout revision under test', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('meta[name="fairmade-source-revision"]')).toHaveAttribute('content', process.env.E2E_EXPECTED_REVISION!)
})

test('administrator approves seller and denies another application through the real website', async ({ page }) => {
  const api = await signIn(page, 'admin')
  await page.getByRole('link', { name: 'Review seller applications' }).click()
  await page.getByRole('link', { name: 'browser-seller@example.com', exact: true }).click()
  await field(page, 'application-outcome', 'approved')
  await field(page, 'application-reason', 'Synthetic local browser acceptance seller; no identity or quality certification.')
  page.once('dialog', dialog => dialog.accept())
  await posted(page, '/decision', () => page.getByRole('button', { name: 'Record final application decision' }).click())
  await expect(page.getByText(/Final decision: approved/)).toBeVisible()
  await page.getByRole('link', { name: 'Back to application queue' }).click()
  await page.getByRole('link', { name: 'browser-denied@example.com', exact: true }).click()
  await field(page, 'application-outcome', 'denied')
  await field(page, 'application-reason', 'Synthetic denial to exercise the terminal decision workflow.')
  page.once('dialog', dialog => dialog.accept())
  await posted(page, '/decision', () => page.getByRole('button', { name: 'Record final application decision' }).click())
  await expect(page.getByText(/Final decision: denied/)).toBeVisible()
  await api.dispose()
})
