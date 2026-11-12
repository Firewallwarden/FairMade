import assert from 'node:assert/strict'
import { test } from 'node:test'
import { decodeEditablePassport } from '../src/services/passport-contract.ts'

const content = {
  review_id: 'private-review', title: 'Saved title', price: '8.25', public_description: null,
  composition: null,
  disclosures: {
    cost_categories: ['materials'], include_labor: false, include_unit_cost: true,
    include_quality_requirements: false, include_quality_summary: true,
    include_market_context: false, include_composition: false,
  },
}
test('loading a draft preserves opt-in disclosures, price precision and concurrency revision', () => {
  const draft = decodeEditablePassport({ id: 'draft', revision: 7, content })
  assert.equal(draft.revision, 7)
  assert.deepEqual(draft.content, content)
})
test('draft disclosure booleans and cost categories reject malformed server data', () => {
  for (const disclosures of [
    { ...content.disclosures, include_labor: 'false' },
    { ...content.disclosures, cost_categories: ['secret_recipe'] },
  ]) assert.throws(() => decodeEditablePassport({ id: 'draft', revision: 1, content: { ...content, disclosures } }))
})
