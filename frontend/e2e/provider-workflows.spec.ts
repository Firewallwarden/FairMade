import { test, expect, request } from './fixtures'
import { readFileSync } from 'node:fs'
import { randomUUID } from 'node:crypto'
import { signIn, apiForRole, seedListing, field, posted } from './helpers'
import type { Page } from '@playwright/test'
import { openProduct } from './helpers'

// Provider sign-in and receipt details must not appear in screenshots or traces.
test.use({ screenshot: 'off', trace: 'off' })

async function signInReceiptSeller(page: Page) {
  // Each project must import independently without bypassing receipt deduplication.
  const reviewer = await apiForRole('admin')
  const credentials = { email: `receipt-${randomUUID()}@example.com`, password: process.env.E2E_PASSWORD! }
  const registration = await reviewer.post('auth/register', { data: credentials })
  expect(registration.status()).toBe(201)
  const login = await reviewer.post('auth/login', { data: credentials })
  expect(login.ok()).toBeTruthy()
  const token = await login.json()
  const seller = await request.newContext({
    baseURL: `http://127.0.0.1:${process.env.E2E_API_PORT ?? '8002'}/api/v1/`,
    extraHTTPHeaders: { Authorization: `Bearer ${token.access_token}` },
  })
  const applicationResponse = await seller.post('seller-applications', { data: {} })
  expect(applicationResponse.ok()).toBeTruthy()
  const application = await applicationResponse.json()
  const approval = await reviewer.post(`admin/seller-applications/${application.id}/decision`, {
    data: { expected_revision: application.revision, outcome: 'approved', reason: 'Isolated synthetic receipt browser acceptance seller.' },
  })
  expect(approval.ok()).toBeTruthy()
  await reviewer.dispose()
  await page.goto('/#/account')
  await page.getByLabel('Email', { exact: true }).fill(credentials.email)
  await page.getByLabel(/^Password/).fill(credentials.password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).last().click()
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeVisible()
  return seller
}

test('real local description draft is reviewed, edited and applied privately', async ({ page }) => {
  test.skip(process.env.E2E_PROVIDERS !== '1', 'Requires the real local model explicitly enabled.')
  test.setTimeout(240_000)
  const api = await signIn(page)
  const { product } = await seedListing(api)
  await openProduct(page, product.id, 'Photos & description')
  const draft = await posted(page, '/description-drafts', () => page.getByRole('button', { name: 'Generate private draft', exact: true }).click())
  await page.getByRole('textbox', { name: 'Review and edit the description', exact: true }).fill('Synthetic seller-reviewed bread description. Claims remain unverified.')
  await posted(page, `/description-drafts/${draft.id}`, () => page.getByRole('button', { name: 'Save edited draft', exact: true }).click())
  await page.getByLabel('I reviewed this exact text and its factual claims.', { exact: true }).check()
  await posted(page, '/approve', () => page.getByRole('button', { name: 'Approve & apply privately', exact: true }).click())
  const saved = await (await api.get(`products/${product.id}`)).json()
  expect(saved.description).toBe('Synthetic seller-reviewed bread description. Claims remain unverified.')
  await api.dispose()
})

test('real receipt image extraction, seller corrections and approval create a recorded expense', async ({ page }) => {
  test.skip(process.env.E2E_PROVIDERS !== '1' || !process.env.E2E_RECEIPT_IMAGE || !process.env.E2E_RECEIPT_REVIEW, 'Requires Ollama/Tesseract plus E2E_RECEIPT_IMAGE and a private reviewed-value JSON file E2E_RECEIPT_REVIEW.')
  test.setTimeout(360_000)
  const review = JSON.parse(readFileSync(process.env.E2E_RECEIPT_REVIEW!, 'utf8'))
  const api = await signInReceiptSeller(page)
  await page.goto('/#/receipts')
  await page.locator('[name="receipt-image"]').setInputFiles(process.env.E2E_RECEIPT_IMAGE!)
  const pending = page.waitForResponse(r => r.url().endsWith('/seller/receipt-drafts') && r.request().method() === 'POST', { timeout: 180_000 })
  await page.getByRole('button', { name: 'Extract private draft', exact: true }).click()
  const extracted = await pending
  expect(extracted.ok()).toBeTruthy()
  const draft = await extracted.json()
  await expect(page.getByText(/Saved revision/)).toBeVisible()
  for (const [name, value] of Object.entries({ 'receipt-merchant': review.merchant, 'receipt-date': review.purchased_on, 'receipt-currency': review.currency, 'receipt-category': review.category, 'receipt-subtotal': review.subtotal ?? '', 'receipt-tax': review.tax ?? '', 'receipt-total': review.total })) await field(page, name, String(value))
  // Use a private ground-truth fixture rather than inventing extracted receipt values.
  const itemFields = page.locator('input[name^="receipt-item-"]')
  while (await itemFields.count() < review.items.length) await page.getByRole('button', { name: 'Add line item', exact: true }).click()
  while (await itemFields.count() > review.items.length) await page.getByRole('button', { name: /Remove item/ }).last().click()
  for (let index = 0; index < review.items.length; index++) {
    await itemFields.nth(index).fill(review.items[index].description)
    await page.locator('input[name^="receipt-amount-"]').nth(index).fill(review.items[index].line_total ?? '')
  }
  await posted(page, `/receipt-drafts/${draft.id}`, () => page.getByRole('button', { name: 'Save corrections & preview' }).click())
  await page.locator('[name="approve-receipt"]').check()
  const expense = await posted(page, '/approve', () => page.getByRole('button', { name: 'Approve & record expense' }).click())
  await page.goto('/#/receipts')
  await page.getByRole('button', { name: 'Recorded expenses', exact: true }).click()
  await expect(page.getByRole('heading', { name: review.merchant, exact: true })).toBeVisible()
  const recorded = await api.get('seller/expenses')
  expect(recorded.ok()).toBeTruthy()
  expect((await recorded.json()).items.some((item: { id: string }) => item.id === expense.id)).toBeTruthy()
  await api.dispose()
})

async function approvePayPal(page: Page) {
  const popupPromise = page.waitForEvent('popup')
  await page.frameLocator('iframe[title="PayPal"]').locator('[data-funding-source="paypal"]').click()
  const popup = await popupPromise
  await popup.waitForURL(/https:\/\/(www\.)?sandbox\.paypal\.com\//)
  await popup.locator('#email').fill(process.env.E2E_PAYPAL_BUYER_EMAIL!)
  const next = popup.locator('#btnNext')
  if (await next.isVisible()) await next.click()
  await popup.locator('#password').fill(process.env.E2E_PAYPAL_BUYER_PASSWORD!)
  await popup.locator('#btnLogin').click()
  await popup.locator('#payment-submit-btn').click()
  await expect(page.getByText(/backend verified a completed PayPal sandbox capture/i)).toBeVisible({ timeout: 120_000 })
}

for (const outcome of ['approve', 'deny'] as const) {
  test(`real PayPal sandbox purchase, pickup history and ${outcome} refund workflow`, async ({ page, browser }) => {
    test.skip(process.env.E2E_PAYPAL !== '1' || !process.env.E2E_PAYPAL_BUYER_EMAIL || !process.env.E2E_PAYPAL_BUYER_PASSWORD, 'Requires sandbox backend credentials and private E2E_PAYPAL_BUYER_EMAIL/PASSWORD. No real payment data or mocked completion.')
    test.setTimeout(480_000)
    const sellerApi = await apiForRole('seller')
    const { listing, product } = await seedListing(sellerApi)
    const buyerApi = await signIn(page, 'buyer')
    await page.goto(`/#/market/${listing.id}`)
    await posted(page, '/orders/preview', () => page.getByRole('button', { name: 'Review purchase subtotal' }).click())
    const order = await posted(page, '/orders', () => page.getByRole('button', { name: 'Reserve stock & continue' }).click())
    await approvePayPal(page)
    await page.getByText(`Review your sandbox purchase: ${product.name}`, { exact: true }).click()
    await field(page, 'review-rating', '4')
    await field(page, 'review-text', 'Synthetic sandbox buyer opinion; no independent quality verification.')
    await page.locator('[name="review-publish"]').check()
    const review = await posted(page, `/listings/${listing.id}/review`, () => page.getByRole('button', { name: 'Publish approved review' }).click())
    await page.goto('/#/reviews')
    const own = page.getByRole('article').filter({ hasText: listing.id.slice(0, 8) })
    await own.locator('[name="review-text"]').fill('Edited synthetic sandbox buyer opinion.')
    await own.locator('[name="review-publish"]').check()
    await posted(page, `/account/product-reviews/${review.id}`,
      () => own.getByRole('button', { name: 'Save approved public changes' }).click())
    await own.getByRole('button', { name: 'Withdraw this public review' }).click()
    await expect(own.getByRole('button', { name: 'Approve & republish review' })).toBeVisible()
    await page.goto(`/#/orders/${order.id}`)
    const sellerContext = await browser.newContext({ baseURL: new URL(page.url()).origin })
    const sellerPage = await sellerContext.newPage()
    const sellerSession = await signIn(sellerPage)
    await sellerPage.goto(`/#/seller-orders/${order.id}`)
    for (const state of ['preparing', 'ready_for_pickup', 'collected']) {
      await field(sellerPage, 'pickup-state', state)
      await field(sellerPage, 'pickup-instructions', 'Synthetic sandbox pickup instructions; no real address')
      await posted(sellerPage, '/fulfillment', () => sellerPage.getByRole('button', { name: 'Save seller-reported pickup state' }).click())
      await expect(sellerPage.getByText('Seller-reported status:', { exact: false })).toContainText(state.replaceAll('_', ' '))
    }
    await page.getByRole('button', { name: 'Refresh pickup', exact: true }).click()
    await expect(page.getByText(/revision 3/)).toBeVisible()
    await field(page, 'refund-reason', 'Synthetic sandbox browser acceptance refund')
    await posted(page, '/refund-request', () => page.getByRole('button', { name: 'Request seller-reviewed refund' }).click())
    await page.goto('/#/orders')
    await page.getByRole('button', { name: 'My refund requests', exact: true }).click()
    await page.getByRole('link', { name: `Order ${order.id}`, exact: true }).click()
    await sellerPage.goto('/#/orders')
    await sellerPage.getByRole('button', { name: 'My seller orders', exact: true }).click()
    await sellerPage.getByRole('button', { name: 'Seller refund inbox', exact: true }).click()
    await sellerPage.getByRole('link', { name: `Order ${order.id}`, exact: true }).click()
    await sellerPage.getByRole('button', { name: 'Refresh refund & order status' }).click()
    if (outcome === 'approve') {
      // Lose the browser response after the real backend processes the refund.
      await sellerPage.route('**/refund-request/approve', async route => { await route.fetch(); await route.abort('failed') })
      await sellerPage.locator('[name="approve-refund"]').check()
      await sellerPage.getByRole('button', { name: 'Approve & request sandbox refund' }).click()
      await sellerPage.unroute('**/refund-request/approve')
      await sellerPage.getByRole('button', { name: 'Refresh refund & order status' }).click()
      const verify = sellerPage.getByRole('button', { name: 'Verify refund with PayPal' })
      if (await verify.isVisible()) await verify.click()
      await expect.poll(async () => (await (await buyerApi.get(`orders/${order.id}/refund-request`)).json()).state, { timeout: 120_000 }).toBe('refunded')
    } else {
      await sellerPage.getByText('Deny the request with a shared reason', { exact: false }).click()
      await field(sellerPage, 'refund-denial', 'Synthetic denial browser acceptance case')
      await posted(sellerPage, '/deny', () => sellerPage.getByRole('button', { name: 'Deny refund request' }).click())
      await expect.poll(async () => (await (await buyerApi.get(`orders/${order.id}/refund-request`)).json()).state).toBe('denied')
    }
    await page.getByRole('button', { name: 'Refresh refund & order status' }).click()
    await expect(page.getByText(outcome === 'approve' ? /refunded/ : /denied/).first()).toBeVisible()
    await sellerContext.close(); await sellerApi.dispose(); await sellerSession.dispose(); await buyerApi.dispose()
  })
}
