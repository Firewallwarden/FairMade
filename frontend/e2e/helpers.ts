import { expect, request } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'
import { appendFileSync } from 'node:fs'
import { join } from 'node:path'

const audited = new WeakSet<Page>()
export function auditBrowserRequests(page: Page) {
  if (audited.has(page)) return
  audited.add(page)
  page.on('response', response => {
    const path = new URL(response.url()).pathname
    if (!path.startsWith('/api/v1/')) return
    // Record only methods, sanitized route templates and statuses, never tokens,
    // request bodies, queries, receipt values or model answers.
    const route = path.replace(/[a-f0-9]{8}-[a-f0-9-]{27,}/gi, '{id}')
    appendFileSync(join(process.env.E2E_RUN_DIR!, 'browser-endpoints.jsonl'), JSON.stringify({ method: response.request().method(), route, status: response.status() }) + '\n')
  })
}

export async function signIn(page: Page, role: 'admin' | 'buyer' | 'seller' | 'denied' = 'seller') {
  auditBrowserRequests(page)
  await page.goto('/#/account')
  await page.getByLabel('Email', { exact: true }).fill(`browser-${role}@example.com`)
  await page.getByLabel(/^Password/).fill(process.env.E2E_PASSWORD!)
  const response = page.waitForResponse(r => r.url().endsWith('/api/v1/auth/login') && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Sign in', exact: true }).last().click()
  const token = await (await response).json()
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeVisible()
  return request.newContext({ baseURL: `http://127.0.0.1:${process.env.E2E_API_PORT ?? '8002'}/api/v1/`, extraHTTPHeaders: { Authorization: `Bearer ${token.access_token}` } })
}
export async function field(page: Page, name: string, value: string) {
  const element = page.locator(`[name="${name}"]`)
  if (await element.evaluate(el => el.tagName === 'SELECT')) await element.selectOption(value)
  else await element.fill(value)
}
export async function posted(page: Page, suffix: string, action: () => Promise<unknown>) {
  const modelRequest = ['/turns', '/description-drafts', '/remember'].some(path => suffix.endsWith(path))
  const [response] = await Promise.all([
    page.waitForResponse(r => new URL(r.url()).pathname.endsWith(suffix) && ['POST', 'PUT', 'PATCH'].includes(r.request().method()), { timeout: modelRequest ? 150_000 : 15_000 }),
    action(),
  ])
  expect(response.ok(), `${response.request().method()} ${suffix} returned ${response.status()}`).toBeTruthy()
  return response.status() === 204 ? null : response.json()
}
export async function createProduct(api: APIRequestContext, label = 'Synthetic browser bread') {
  const response = await api.post('products', { data: { name: `${label} ${crypto.randomUUID().slice(0, 8)}`, product_type: 'sourdough', selling_unit: 'loaf', description: 'Synthetic browser evidence only' } })
  expect(response.status()).toBe(201)
  return response.json()
}
export const economics = {
  currency: 'USD', sellable_units: 10, costs: [{ label: 'Synthetic flour', category: 'materials', amount: '10.00' }], labor: [],
  payment_fees: { rate: '0.03', fixed_per_order: '0.30', units_per_order: 1 }, target_margin: { minimum: '0.20', maximum: '0.30' }, proposed_prices: ['4.00'],
}
export async function seedAnalysis(api: APIRequestContext, productId: string) {
  const response = await api.post(`products/${productId}/analyses`, { data: economics })
  expect(response.status()).toBe(201)
  return response.json()
}
export async function chooseHistory(page: Page, title: string, id?: string) {
  const picker = page.getByRole('group', { name: title, exact: true })
  await expect(picker.locator('select option')).not.toHaveCount(1)
  const select = picker.locator('select')
  const value = id ?? await select.locator('option').nth(1).getAttribute('value')
  await select.selectOption(value!)
  return value!
}
export async function openProduct(page: Page, id: string, tool?: string) {
  await page.goto(`/#/seller/${id}`)
  await expect(page.getByRole('heading', { name: 'Your saved cost picture' })).toBeVisible()
  if (tool) await page.getByRole('button', { name: tool, exact: true }).click()
}

// Setup through documented HTTP APIs; assertions in specs still exercise website actions.
export async function apiForRole(role: 'buyer' | 'seller' | 'admin') {
  const api = await request.newContext({ baseURL: `http://127.0.0.1:${process.env.E2E_API_PORT ?? '8002'}/api/v1/` })
  const response = await api.post('auth/login', { data: { email: `browser-${role}@example.com`, password: process.env.E2E_PASSWORD } })
  expect(response.ok()).toBeTruthy()
  const { access_token } = await response.json()
  await api.dispose()
  return request.newContext({ baseURL: `http://127.0.0.1:${process.env.E2E_API_PORT ?? '8002'}/api/v1/`, extraHTTPHeaders: { Authorization: `Bearer ${access_token}` } })
}
export async function seedListing(api: APIRequestContext) {
  const product = await createProduct(api)
  const analysis = await seedAnalysis(api, product.id)
  const review = await (await api.post(`products/${product.id}/pricing-reviews`, { data: { pricing_analysis_id: analysis.id } })).json()
  const draftResponse = await api.post(`products/${product.id}/passports`, { data: { review_id: review.id, title: product.name, price: '4.00', disclosures: {} } })
  expect(draftResponse.ok()).toBeTruthy()
  const draft = await draftResponse.json()
  const preview = await (await api.get(`products/${product.id}/passports/${draft.id}/preview`)).json()
  const publication = await (await api.post(`products/${product.id}/passports/${draft.id}/publish`, { data: { expected_revision: preview.revision, preview_hash: preview.preview_hash, approved: true } })).json()
  await api.put(`products/${product.id}/inventory`, { data: { expected_revision: 0, selling_unit: 'loaf', on_hand: 50 } })
  const listing = await (await api.post(`products/${product.id}/listing`, { data: { passport_publication_id: publication.id, seller_display_name: 'Synthetic browser maker', location: 'Synthetic town', selling_quantity: { value: '1', unit: 'loaf' } } })).json()
  const listingPreview = await (await api.get(`products/${product.id}/listing/preview`)).json()
  const activated = await api.post(`products/${product.id}/listing/activate`, { data: { expected_revision: listingPreview.revision, preview_hash: listingPreview.preview_hash, approved: true } })
  expect(activated.ok()).toBeTruthy()
  return { product, listing, publication, draft, review, analysis }
}
