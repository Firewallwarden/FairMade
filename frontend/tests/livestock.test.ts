import test from 'node:test'
import assert from 'node:assert/strict'
import {
  decodeGroup,
  decodeLivestockHistory,
  decodeAnimal,
} from '../src/services/livestock-contract.ts'
test('observed headcount stays separate from registered animals and unknown stays unknown', () => {
  const profile = {
    id: 'group',
    species: 'Chicken',
    name: 'Flock',
    breed: null,
    notes: null,
    reported_headcount: null,
    headcount_on: null,
    archived: false,
    revision: 1,
    registered_active_animals: 2,
    basis: 'seller_reported_unverified',
  }
  assert.equal(decodeGroup(profile).reported_headcount, null)
  assert.equal(
    decodeGroup({
      ...profile,
      reported_headcount: 10,
      headcount_on: '2026-11-11',
    }).registered_active_animals,
    2,
  )
})
test('livestock change responses identify their resource and preserve original snapshots', () => {
  const event = decodeLivestockHistory({
    id: 'event',
    resource_id: 'animal',
    revision: 2,
    occurred_on: '2026-11-11',
    reason: 'Correction',
    before: { status: 'active' },
    after: { status: 'departed' },
    created_at: '2026-11-11T10:00:00Z',
    basis: 'seller_reported_unverified',
  })
  assert.equal(event.resource_id, 'animal')
  assert.equal(event.before?.status, 'active')
  assert.equal(event.after.status, 'departed')
  assert.throws(() =>
    decodeAnimal({
      id: 'animal',
      species: 'Chicken',
      revision: 1,
      basis: 'verified',
    }),
  )
})
