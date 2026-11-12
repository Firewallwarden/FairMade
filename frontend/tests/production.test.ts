import assert from 'node:assert/strict'
import { test } from 'node:test'
import { rateAsPercent, readBatchEntries } from '../src/utils/batch-entries.ts'
import { percentToRate } from '../src/services/pricing-contract.ts'
import { decodeProduction } from '../src/services/production-contract.ts'
test('saved recipe rates round-trip to percentages without floating-point money arithmetic', () => {
  for (const rate of ['0', '0.03', '0.2', '0.123456', '0.000001'])
    assert.equal(percentToRate(rateAsPercent(rate)), rate)
})
test('batch inputs preserve exact decimal strings and do not invent omitted expense rows', () => {
  const fields = new FormData()
  assert.deepEqual(readBatchEntries(fields, 'batch'), { costs: [], labor: [] })
  fields.set('batch-cost-row', 'one')
  fields.set('batch-cost-label-one', 'Packaging')
  fields.set('batch-cost-category-one', 'packaging')
  fields.set('batch-cost-amount-one', '0.123456')
  assert.equal(readBatchEntries(fields, 'batch').costs[0].amount, '0.123456')
})
test('zero sellable production yield never becomes a zero unit-cost claim', () => {
  const record = decodeProduction({
    id: 'synthetic',
    label: 'Failed batch',
    kind: 'batch',
    started_on: '2026-11-11',
    completed_on: '2026-11-11',
    selling_unit: 'loaf',
    total_units: 10,
    sellable_units: 0,
    corrects_record_id: null,
    product_snapshot: {},
    request: {},
    livestock_snapshot: null,
    result: {
      calculation_version: 'completed-production-costs-v1',
      batch_total: '20.00',
      labor_total: '0.00',
      unit_cost: null,
      unsellable_units: 10,
      yield_fraction: '0',
      category_totals: {},
      warnings: [],
    },
  })
  assert.equal(record.result.unit_cost, null)
  assert.equal(record.result.batch_total, '20.00')
})
