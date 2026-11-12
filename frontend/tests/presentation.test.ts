import assert from 'node:assert/strict'
import { test } from 'node:test'
import { decodeStorefrontContent, validatePhoto } from '../src/services/presentation-contract.ts'

test('uploads reject unsupported, empty and oversized images before transport', () => {
  assert.doesNotThrow(() => validatePhoto({ type: 'image/png', size: 1024 }))
  assert.throws(() => validatePhoto({ type: 'image/svg+xml', size: 1024 }))
  assert.throws(() => validatePhoto({ type: 'image/jpeg', size: 0 }))
  assert.throws(() => validatePhoto({ type: 'image/jpeg', size: 5 * 1024 * 1024 + 1 }))
})
test('public areas remain explicit approximate seller declarations', () => {
  const profile = decodeStorefrontContent({ display_name: 'Synthetic farm', approximate_area: { label: 'Town center', latitude: '40.12', longitude: '-89.12', basis: 'seller_chosen_approximate' } })
  assert.equal(profile.approximate_area?.basis, 'seller_chosen_approximate')
  assert.equal(profile.location, null)
  assert.throws(() => decodeStorefrontContent({ display_name: 'Farm', approximate_area: { basis: 'verified_address' } }))
})
