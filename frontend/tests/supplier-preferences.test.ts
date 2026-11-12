import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  readAdditionalClaims,
  readOptionalPreferences,
} from '../src/utils/optional-preferences.ts'
test('optional quote attributes cannot overwrite even an unanswered mandatory claim', () => {
  const fields = new FormData()
  fields.set('quote-extra-row', 'one')
  fields.set('quote-extra-key-one', 'organic')
  fields.set('quote-extra-type-one', 'boolean')
  fields.set('quote-extra-value-one', 'true')
  assert.throws(
    () => readAdditionalClaims(fields, {}, ['organic']),
    /cannot replace/,
  )
  fields.set('quote-extra-key-one', 'delivery')
  assert.deepEqual(readAdditionalClaims(fields, {}, ['organic']), {
    delivery: { type: 'boolean', value: true },
  })
})
test('optional preference order and explicit false are preserved without changing mandatory rules', () => {
  const fields = new FormData()
  fields.append('pref-row', 'one')
  fields.append('pref-row', 'two')
  for (const [row, key, value] of [
    ['one', 'plastic_packaging', 'false'],
    ['two', 'delivery', 'true'],
  ]) {
    fields.set('pref-key-' + row, key)
    fields.set('pref-label-' + row, key)
    fields.set('pref-type-' + row, 'boolean')
    fields.set('pref-expected-' + row, value)
  }
  const result = readOptionalPreferences(fields, 'pref')
  assert.equal(result[0].key, 'plastic_packaging')
  assert.deepEqual(result[0], {
    key: 'plastic_packaging',
    label: 'plastic_packaging',
    type: 'boolean',
    expected: false,
  })
  assert.equal(result[1].key, 'delivery')
})
