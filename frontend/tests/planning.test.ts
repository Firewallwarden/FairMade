import assert from 'node:assert/strict'
import { test } from 'node:test'
import { buildBasketRequest } from '../src/utils/shopping-plan.ts'
import { decodeBasket } from '../src/services/planning-contract.ts'
const alternative = {
  listing_id: 'synthetic-listing',
  expected_listing_revision: 3,
}
test('planning rejects repeated products across needs and fractional selling-unit counts', () => {
  const need = {
    group_id: 'breakfast',
    quantity: 2,
    alternatives: [alternative],
  }
  assert.throws(
    () =>
      buildBasketRequest('store', null, [
        need,
        { ...need, group_id: 'another' },
      ]),
    /only one need/,
  )
  assert.throws(
    () => buildBasketRequest('store', null, [{ ...need, quantity: 1.5 }]),
    /selling units/,
  )
  assert.equal(buildBasketRequest('store', '12.30', [need]).budget, '12.30')
})
test('an over-budget plan has no implied purchase or invented available budget', () => {
  const result = decodeBasket({
    optimization_version: 'single-storefront-basket-v1',
    status: 'over_budget',
    minimum_subtotal: { currency: 'USD', amount: '14.00' },
    remaining_budget: null,
    personalized: false,
    cart: null,
    preview: null,
    notices: [],
    needs: [],
  })
  assert.equal(result.cart, null)
  assert.equal(result.remaining_budget, null)
  assert.equal(result.status, 'over_budget')
})
