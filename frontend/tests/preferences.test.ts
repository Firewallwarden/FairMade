import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  decodeBuyerProfile,
  decodeMemoryProposal,
} from '../src/services/preferences-contract.ts'
const preferences = {
  budget_per_item: '12.00',
  product_types: ['eggs'],
  location: null,
  excluded_listing_ids: [],
}
test('disabled buyer profiles cannot silently retain shopping preferences', () => {
  assert.throws(() => decodeBuyerProfile({ enabled: false, preferences }))
  const disabled = decodeBuyerProfile({
    enabled: false,
    preferences: { ...preferences, budget_per_item: null, product_types: [] },
    revision: 3,
    status: 'disabled',
    expires_at: null,
    notices: [],
  })
  assert.equal(disabled.preferences.budget_per_item, null)
})
test('model memory proposals remain separate from active consent', () => {
  const proposal = decodeMemoryProposal({
    profile_revision: 2,
    preferences,
    notices: [],
  })
  assert.equal(proposal.preferences.budget_per_item, '12.00')
  assert.equal(Object.hasOwn(proposal, 'enabled'), false)
  assert.equal(Object.hasOwn(proposal, 'confirmed'), false)
})
