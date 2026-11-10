import assert from 'node:assert/strict'
import { test } from 'node:test'
import { decodePassport } from '../src/services/catalog-contract.ts'
import {
  decodeOrder,
  decodePayment,
  isVerifiedPaid,
} from '../src/services/order-contract.ts'

const order = {
  id: 'synthetic-order',
  status: 'paid',
  created_at: '2026-11-09T10:00:00Z',
  expires_at: '2026-11-09T10:15:00Z',
  snapshot: {
    order_version: 'unpaid-order-v1',
    items: [],
    subtotal: { currency: 'USD', amount: '8.00' },
    notices: [],
  },
}
const payment = {
  order_id: 'synthetic-order',
  environment: 'sandbox',
  merchant_mode: 'shared',
  state: 'completed',
  capture_id: 'synthetic-capture',
  verified_at: '2026-11-09T10:01:00Z',
  amount: { currency: 'USD', amount: '8.00' },
}

test('payment confirmation requires backend paid state and a matching verified capture', () => {
  const verifiedOrder = decodeOrder(order)
  const verifiedPayment = decodePayment(payment)
  assert.equal(isVerifiedPaid(verifiedOrder, verifiedPayment), true)
  assert.equal(
    isVerifiedPaid(
      decodeOrder({ ...order, status: 'pending_payment' }),
      verifiedPayment,
    ),
    false,
  )
  assert.equal(
    isVerifiedPaid(
      verifiedOrder,
      decodePayment({ ...payment, state: 'ready' }),
    ),
    false,
  )
  assert.equal(
    isVerifiedPaid(
      verifiedOrder,
      decodePayment({ ...payment, capture_id: null }),
    ),
    false,
  )
  assert.equal(
    isVerifiedPaid(
      verifiedOrder,
      decodePayment({ ...payment, verified_at: null }),
    ),
    false,
  )
  assert.equal(
    isVerifiedPaid(
      verifiedOrder,
      decodePayment({ ...payment, order_id: 'other-order' }),
    ),
    false,
  )
  assert.equal(isVerifiedPaid(verifiedOrder, null), false)
})

test('checkout decoder rejects live configuration and invented payment states', () => {
  assert.throws(() => decodePayment({ ...payment, environment: 'live' }))
  assert.throws(() => decodePayment({ ...payment, state: 'approved' }))
  assert.throws(() => decodeOrder({ ...order, status: 'success' }))
})

test('undisclosed Passport costs remain absent, never fabricated as zeros', () => {
  const decoded = decodePassport({
    passport_version: 'fair-price-passport-v1',
    basis: 'seller_reported_unverified',
    reviewed_on: '2026-11-09',
    product: {
      title: 'Synthetic loaf',
      product_type: 'sourdough',
      selling_unit: 'loaf',
    },
    price: { currency: 'USD', amount: '8.00' },
    notices: ['Seller reported.'],
  })
  assert.equal(decoded.costs, null)
  assert.equal(decoded.quality_requirements, null)
  assert.throws(() =>
    decodePassport({ ...decoded, passport_version: 'future' }),
  )
})
