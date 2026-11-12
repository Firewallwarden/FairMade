import { test, expect } from './fixtures'
import { signIn, apiForRole, seedListing, field, posted, chooseHistory } from './helpers'

test('assistant transport failure retains retry identity, unavailable provider invents no answer, deletion is persisted', async ({ page }) => {
  test.skip(process.env.E2E_PROVIDERS === '1', 'This case specifically exercises the disabled-provider backend.')
  const api = await signIn(page, 'buyer')
  const sellerApi = await apiForRole('seller')
  const { listing } = await seedListing(sellerApi)
  await page.goto(`/#/assistant/buyer/${listing.id}`)
  const conversation = await posted(page, '/assistants/conversations', () => page.getByRole('button', { name: 'Start saved conversation' }).click())
  await field(page, 'assistant-question', 'What evidence explains this price?')
  let firstId = ''
  await page.route('**/assistants/conversations/*/turns', async route => {
    firstId = route.request().postDataJSON().request_id
    await route.abort('timedout')
  })
  await page.getByRole('button', { name: 'Ask FairMade', exact: true }).last().click()
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.locator('[name="assistant-question"]')).toHaveValue('What evidence explains this price?')
  await page.unroute('**/assistants/conversations/*/turns')
  const retry = page.waitForResponse(r => r.url().endsWith(`/conversations/${conversation.id}/turns`))
  await page.getByRole('button', { name: 'Retry the same question' }).click()
  const response = await retry
  expect(response.request().postDataJSON().request_id).toBe(firstId)
  expect(response.status()).toBe(503)
  await expect(page.getByRole('alert')).toBeVisible()
  const turns = await (await api.get(`assistants/conversations/${conversation.id}/turns`)).json()
  expect(turns.items).toHaveLength(0)
  await page.getByText('Delete this conversation', { exact: true }).click()
  await page.locator('[name="confirm-delete-conversation"]').check()
  await page.getByRole('button', { name: 'Delete conversation', exact: true }).click()
  await expect(page).toHaveURL(/#\/assistant$/)
  expect((await api.get(`assistants/conversations/${conversation.id}`)).status()).toBe(404)
  await api.dispose(); await sellerApi.dispose()
})

test('revoked sessions clear private assistant access and prompt sign-in', async ({ page }) => {
  const api = await signIn(page, 'seller')
  await api.post('auth/logout')
  await page.goto('/#/assistant')
  await expect(page.getByRole('link', { name: 'Sign in or create an account' })).toBeVisible()
  await api.dispose()
})

for (const role of ['buyer', 'seller'] as const) {
  test(`${role} assistant answers a referential follow-up and reopens saved conversation with real Ollama`, async ({ page }) => {
    test.skip(process.env.E2E_PROVIDERS !== '1', 'Requires local Ollama qwen3:8b explicitly enabled with E2E_PROVIDERS=1.')
    test.setTimeout(360_000)
    const api = await signIn(page, role)
    const sellerApi = await apiForRole('seller')
    const { listing, product, analysis, review } = await seedListing(sellerApi)
    await page.goto(`/#/assistant/${role}/${role === 'buyer' ? listing.id : product.id}`)
    if (role === 'seller') {
      await chooseHistory(page, 'Saved pricing source', analysis.id)
      await page.getByText('Choose more private business context', { exact: true }).click()
      await chooseHistory(page, 'Saved pricing review', review.id)
    }
    const conversation = await posted(page, '/assistants/conversations', () => page.getByRole('button', { name: 'Start saved conversation' }).click())
    await field(page, 'assistant-question', 'Explain which recorded evidence supports this price and what remains unknown.')
    const first = await posted(page, '/turns', () => page.getByRole('button', { name: 'Ask FairMade', exact: true }).last().click())
    expect(first.answer_status).toBe('available')
    await field(page, 'assistant-question', 'In your previous answer, which limitation should I remember before deciding?')
    const followup = await posted(page, '/turns', () => page.getByRole('button', { name: 'Ask FairMade', exact: true }).last().click())
    expect(followup.answer_status).toBe('available')
    await page.goto('/#/market')
    await page.goto(`/#/assistant/conversations/${conversation.id}`)
    await expect(page.getByText('In your previous answer, which limitation should I remember before deciding?', { exact: true })).toBeVisible()
    await expect(page.getByText('Explain which recorded evidence supports this price and what remains unknown.', { exact: true })).toBeVisible()
    if (role === 'buyer') {
      await sellerApi.post(`products/${product.id}/listing/deactivate`)
      await page.getByRole('button', { name: 'Reload history & current source access' }).click()
      await expect(page.getByRole('alert')).toBeVisible()
    }
    await api.dispose(); await sellerApi.dispose()
  })
}
