import { test, expect } from './fixtures'
import { signIn, createProduct, seedAnalysis, openProduct, chooseHistory, field, posted } from './helpers'

test('multiple historical Quality Lock selections remain submitted after paging away', async ({ page }) => {
  const api = await signIn(page)
  const product = await createProduct(api)
  const analysis = await seedAnalysis(api, product.id)
  for (let index = 0; index < 21; index++) {
    const response = await api.post(`products/${product.id}/quality-evaluations`, { data: { candidate_label: `Synthetic historical candidate ${index}`, expected_revision: 0, claims: {} } })
    expect(response.ok()).toBeTruthy()
  }
  await openProduct(page, product.id, '4 · Review & publish')
  await chooseHistory(page, 'Saved analysis', analysis.id)
  const picker = page.getByRole('group', { name: 'Saved quality evaluations', exact: true })
  await picker.getByRole('checkbox').first().check()
  const selected = await picker.locator('input[type="hidden"][name="evaluation"]').inputValue()
  await picker.getByRole('button', { name: 'Next saved quality evaluations' }).click()
  await expect(picker.getByText('Page 2', { exact: true })).toBeVisible()
  await expect(picker.locator(`input[name="evaluation"][value="${selected}"]`)).toHaveCount(1)
  await field(page, 'passport-title', 'Synthetic historical selection')
  await field(page, 'passport-price', '4.00')
  const reviewRequest = page.waitForRequest(r => r.url().endsWith('/pricing-reviews') && r.method() === 'POST')
  await posted(page, '/passports', () => page.getByRole('button', { name: 'Build private review & preview' }).click())
  expect((await reviewRequest).postDataJSON().quality_evaluation_ids).toEqual([selected])
  await api.dispose()
})

test('older sourcing inputs open detail endpoints and quote selections persist across pages', async ({ page }) => {
  const api = await signIn(page)
  const product = await createProduct(api)
  const inputs = []
  for (let index = 0; index < 21; index++) {
    const response = await api.post(`products/${product.id}/sourcing-inputs`, { data: { label: `Synthetic older source ${index}` } })
    expect(response.ok()).toBeTruthy()
    inputs.push(await response.json())
  }
  const input = inputs[0]
  const today = new Date().toISOString().slice(0, 10)
  for (let index = 0; index < 21; index++) {
    const response = await api.post(`products/${product.id}/sourcing-inputs/${input.id}/supplier-quotes`, { data: {
      supplier_name: `Synthetic quote ${index}`, source: { name: 'Synthetic quote document', kind: 'document', reference: 'Browser fixture, not a supplier offer' }, location: 'Synthetic town', observed_on: today, valid_until: null, currency: 'USD', package_price: '4.00', package_quantity: { value: '1', unit: 'kg' }, usable_fraction: '1', minimum_packages: 1, maximum_packages: null, transport_cost: '0', availability: 'available', claims: {}, notes: null,
    } })
    expect(response.ok()).toBeTruthy()
  }
  await openProduct(page, product.id, 'Supplier savings')
  const inputsPicker = page.getByRole('group', { name: 'Sourcing inputs', exact: true })
  await inputsPicker.getByRole('button', { name: 'Next sourcing inputs' }).click()
  await chooseHistory(page, 'Sourcing inputs', input.id)
  await expect(page.getByRole('heading', { name: `Mandatory requirements for ${input.label}` })).toBeVisible()
  const quotes = page.getByRole('group', { name: 'Supplier quotes', exact: true })
  await quotes.getByRole('checkbox').first().check()
  await quotes.getByRole('button', { name: 'Next supplier quotes' }).click()
  await expect(quotes.getByText('Page 2', { exact: true })).toBeVisible()
  await quotes.getByRole('checkbox', { name: /^Synthetic quote 0\b/ }).check()
  await expect(quotes.locator('input[name="supplier-quote"]')).toHaveCount(2)
  await field(page, 'required-supply-quantity', '1')
  await field(page, 'required-supply-unit', 'kg')
  const reportRequest = page.waitForRequest(r => r.url().endsWith('/supplier-comparisons') && r.method() === 'POST')
  await posted(page, '/supplier-comparisons', () => page.getByRole('button', { name: 'Compare & save supplier report' }).click())
  expect((await reportRequest).postDataJSON().quote_ids).toHaveLength(2)
  await api.dispose()
})
