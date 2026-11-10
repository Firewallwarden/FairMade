import assert from 'node:assert/strict'
import { test } from 'node:test'
import { decodePricing, percentToRate } from '../src/services/pricing-contract.ts'

const response = {
  calculation_version: 'production-economics-v1', currency: 'USD', basis: 'seller_supplied_unverified',
  costs: { category_totals: { materials: '50.000000' }, labor_total: '30.000000', batch_total: '100.000000', unit_cost: '10.000000' },
  fixed_fee_per_unit: '0.250000', break_even_price: '10.57', sustainable_price_range: { minimum: '13.32', maximum: '15.30' },
  scenarios: [{ price: '0', processing_fee_per_unit: '0.250000', profit_per_unit: '-10.250000', batch_profit: '-102.500000', margin: null, markup: '-1.000000', below_break_even: true, below_target_margin: true }],
  warnings: [{ code: 'UNVERIFIED_INPUTS', message: 'Seller supplied.' }], assumptions: ['USD only.'],
}

test('percentage conversion preserves exact fractional rates', () => {
  for (const [input, expected] of [['0', '0'], ['3', '0.03'], ['20', '0.2'], ['2.99', '0.0299'], ['0.0001', '0.000001'], ['99.9999', '0.999999']]) {
    assert.equal(percentToRate(input), expected)
  }
  for (const input of ['100', '-2', '1e1', '', 'NaN', '2.99999']) assert.throws(() => percentToRate(input))
})

test('accepts backend decimal strings, zero-price null margins and losses', () => {
  assert.equal(decodePricing(response).costs.unit_cost, '10.000000')
  assert.equal(decodePricing(response).scenarios[0].margin, null)
  assert.equal(decodePricing(response).scenarios[0].profit_per_unit, '-10.250000')
})

test('rejects incompatible versions, numeric money and incomplete responses', () => {
  assert.throws(() => decodePricing({ ...response, currency: 'EUR' }))
  assert.throws(() => decodePricing({ ...response, calculation_version: 'future-version' }))
  assert.throws(() => decodePricing({ ...response, break_even_price: 10.57 }))
  assert.throws(() => decodePricing({ ...response, costs: null }))
  assert.throws(() => decodePricing({ ...response, warnings: [null] }))
  assert.throws(() => decodePricing({ ...response, scenarios: [{ ...response.scenarios[0], below_break_even: 'true' }] }))
})
