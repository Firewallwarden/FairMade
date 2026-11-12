import assert from 'node:assert/strict'
import { test } from 'node:test'
import { decodeRefund, isVerifiedRefund, decodeMessages, decodePickup } from '../src/services/order-care-contract.ts'

const refund = { id: 'refund', revision: 1, state: 'refunded', reason: 'Synthetic test', decision: 'approved', decision_reason: null, environment: 'sandbox', amount: { currency: 'USD', amount: '8.00' }, provider_refund_id: 'synthetic-receipt', verified_at: '2026-11-11T12:00:00Z' }
test('seller approval and pending refunds never become completion claims', () => {
  assert.equal(isVerifiedRefund(decodeRefund(refund)), true)
  assert.equal(isVerifiedRefund(decodeRefund({ ...refund, state: 'refund_pending' })), false)
  assert.equal(isVerifiedRefund(decodeRefund({ ...refund, verified_at: null })), false)
  assert.equal(isVerifiedRefund(decodeRefund({ ...refund, provider_refund_id: null })), false)
  assert.throws(() => decodeRefund({ ...refund, environment: 'live' }))
})
test('private messages keep participant labels and remain plain text', () => {
  const data = decodeMessages({ items: [{ id: 'message', sequence: 1, sender: 'buyer', is_mine: true, text: '<script>untrusted</script>', created_at: '2026-11-11T12:00:00Z' }], next_after_sequence: 1, has_more: false, notices: [] })
  assert.equal(data.items[0].text, '<script>untrusted</script>')
  assert.throws(() => decodePickup({ basis: 'verified_handoff', revision: 1, state: 'collected', updates_allowed: true, notices: [] }))
})
