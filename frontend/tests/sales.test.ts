import assert from 'node:assert/strict'
import { test } from 'node:test'
import { decodeSalesOrder } from '../src/services/sales-contract.ts'
test('itemized sales preserve unknown fee, cost, profit and margin without zero-filling', () => {
  const result = decodeSalesOrder({ environment: 'sandbox', merchant_mode: 'shared', currency: 'USD', order_id: 'order', created_at: '2026-11-12T00:00:00Z', captured_at: '2026-11-12T00:01:00Z', gross_sales: '8.25', completed_refunds: '0.00', processing_fee: null, fee_basis: 'unavailable', after_refunds_and_fee: null, estimated_production_cost: null, estimated_profit: null, estimated_margin: null, profit_unavailable_reasons: ['PROCESSING_FEE_UNAVAILABLE'], cost_snapshot: null, warnings: [] })
  assert.equal(result.processing_fee, null)
  assert.equal(result.estimated_production_cost, null)
  assert.equal(result.estimated_profit, null)
  assert.equal(result.estimated_margin, null)
  assert.deepEqual(result.profit_unavailable_reasons, ['PROCESSING_FEE_UNAVAILABLE'])
})
