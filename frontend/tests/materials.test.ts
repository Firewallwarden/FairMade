import assert from 'node:assert/strict'
import { test } from 'node:test'
import { decodeMaterialMovement } from '../src/services/material-contract.ts'
test('physical-count adjustments preserve authoritative before/after balances instead of adding counts in the browser', () => {
  const result = decodeMaterialMovement({
    id: 'synthetic',
    revision: 3,
    kind: 'adjustment',
    material_name: 'Flour',
    unit: 'g',
    before: '3000',
    after: '2000',
    delta: '-1000',
    request: { quantity: '2', unit: 'kg' },
    created_at: '2026-11-12T00:00:00Z',
    basis: 'seller_reported_unverified',
  })
  assert.equal(result.after, '2000')
  assert.equal(result.delta, '-1000')
  assert.equal(result.request.quantity, '2')
})
