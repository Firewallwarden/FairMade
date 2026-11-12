import assert from 'node:assert/strict'
import { test } from 'node:test'
import { decodeOrdering } from '../src/services/market-contract.ts'
import { readComposition } from '../src/utils/composition.ts'
test('catalog ordering preserves not-compared evidence rather than implying a price ranking', () => {
  const result = decodeOrdering({
    policy_version: 'catalog-ordering-v1',
    mode: 'unit_price',
    candidate_count: 1,
    compared_count: 0,
    not_compared_count: 1,
    reference_unit: 'loaf',
    notices: [],
    items: [
      {
        listing_id: 'listing',
        quality_status: 'undisclosed',
        comparison_status: 'not_compared',
        reasons: ['missing_quantity'],
      },
    ],
  })
  assert.equal(result?.items[0].comparison_status, 'not_compared')
  assert.equal(result?.items[0].quality_status, 'undisclosed')
})
test('composition is excluded without explicit disclosure and never inferred from private inputs', () => {
  const fields = new FormData()
  fields.set('composition-row', 'one')
  fields.set('composition-label-one', 'Flour')
  assert.equal(readComposition(fields), null)
  fields.set('include_composition', 'on')
  fields.set('composition-completeness', 'partial')
  fields.set('composition-kind-one', 'ingredient')
  fields.set('composition-quantity-one', '500')
  assert.throws(() => readComposition(fields), /both declared quantity/)
  fields.set('composition-unit-one', 'g')
  assert.deepEqual(readComposition(fields)?.items[0].declared_quantity, {
    value: '500',
    unit: 'g',
  })
})
