import assert from 'node:assert/strict'
import { test } from 'node:test'
import { sellerConversationScope } from '../src/utils/assistant-scope.ts'

test('seller context excludes unselected private sources and recipe inputs', () => {
  const fields = new FormData()
  fields.set('assistant-insight-days', '30')
  assert.deepEqual(sellerConversationScope('product', fields), {
    role: 'seller',
    product_id: 'product',
    include_recipe_inputs: false,
  })
})
test('supplier recommendation context requires an explicitly selected report', () => {
  const fields = new FormData()
  fields.set('assistant-recommendations', 'on')
  fields.set('assistant-priority', 'balanced')
  fields.set('assistant-objective', 'purchase_outlay')
  assert.throws(
    () => sellerConversationScope('product', fields),
    /supplier report/,
  )
  fields.set('assistant-supplier-report', 'selected-report')
  assert.deepEqual(sellerConversationScope('product', fields).recommendations, {
    mode: 'balanced',
    cost_objective: 'purchase_outlay',
    preferences: [],
  })
})
test('context windows reject invalid dates and out-of-contract forecast ranges', () => {
  const fields = new FormData()
  fields.set('assistant-history', 'on')
  fields.set('assistant-history-start', '2026-02-30')
  fields.set('assistant-history-end', '2026-03-03')
  assert.throws(() => sellerConversationScope('product', fields), /history end/)
  fields.set('assistant-history-start', '2026-02-28')
  assert.deepEqual(sellerConversationScope('product', fields).history_period, {
    start_date: '2026-02-28',
    end_date: '2026-03-03',
  })
  fields.set('assistant-forecast', 'on')
  fields.set('assistant-lookback', '0')
  fields.set('assistant-horizon', '7')
  assert.throws(
    () => sellerConversationScope('product', fields),
    /whole number/,
  )
})
