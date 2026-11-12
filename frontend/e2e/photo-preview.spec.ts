import { test, expect } from './fixtures'
import { signIn, seedListing, openProduct, chooseHistory, field, posted } from './helpers'

test('new listing photos render privately in preview before they become publicly accessible', async ({ page, browser }) => {
  const api = await signIn(page)
  const { product, listing, draft } = await seedListing(api)
  const dataUrl = await page.evaluate(() => {
    const canvas = document.createElement('canvas'); canvas.width = 16; canvas.height = 16
    canvas.getContext('2d')!.fillRect(0, 0, 16, 16)
    return canvas.toDataURL('image/png')
  })
  const photoResponse = await api.post(`products/${product.id}/photos`, { data: Buffer.from(dataUrl.split(',')[1], 'base64'), headers: { 'Content-Type': 'image/png' } })
  expect(photoResponse.ok()).toBeTruthy()
  const photo = await photoResponse.json()
  expect((await api.get(`marketplace/photos/${photo.id}`)).status()).toBe(404)
  await openProduct(page, product.id, '4 · Review & publish')
  await page.getByText('Recover a previous Passport draft or publication', { exact: true }).click()
  await chooseHistory(page, 'Passport drafts', draft.id)
  await page.locator('[name="listing-photo"]').check()
  await field(page, `photo-alt-${photo.id}`, 'Synthetic browser photo')
  await posted(page, '/listing', () => page.getByRole('button', { name: 'Save & preview listing' }).click())
  const preview = page.getByRole('region', { name: 'Public listing preview' })
  const image = preview.getByRole('img', { name: 'Synthetic browser photo' })
  await expect.poll(() => image.evaluate(el => (el as HTMLImageElement).naturalWidth)).toBeGreaterThan(0)
  expect((await api.get(`marketplace/photos/${photo.id}`)).status()).toBe(404)
  await page.locator('[name="approve-listing"]').check()
  await posted(page, '/activate', () => page.getByRole('button', { name: 'Publish approved listing' }).click())
  const visitor = await browser.newContext({ baseURL: new URL(page.url()).origin })
  const publicPage = await visitor.newPage()
  await publicPage.goto(`/#/market/${listing.id}`)
  const publicImage = publicPage.getByRole('img', { name: 'Synthetic browser photo', exact: true })
  await expect.poll(() => publicImage.evaluate(el => (el as HTMLImageElement).naturalWidth)).toBeGreaterThan(0)
  await visitor.close(); await api.dispose()
})
