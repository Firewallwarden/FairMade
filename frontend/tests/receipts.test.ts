import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  decodeExpenseDetails,
  decodeReceipt,
  validateReceiptImage,
} from '../src/services/receipt-contract.ts'

const details = {
  merchant: null,
  purchased_on: null,
  currency: null,
  subtotal: null,
  tax: null,
  total: '10.00',
  items: [{ description: 'Flour', line_total: null }],
  category: 'materials',
}
test('receipt unknowns stay unknown rather than becoming zero amounts or an assumed currency', () => {
  const result = decodeExpenseDetails(details)
  assert.equal(result.tax, null)
  assert.equal(result.currency, null)
  assert.equal(result.items[0].line_total, null)
  assert.throws(() => decodeExpenseDetails({ ...details, total: 10 }))
})
test('receipt review retains backend blockers and requires a valid saved-preview hash', () => {
  const draft = {
    id: 'synthetic-draft',
    revision: 2,
    state: 'draft',
    created_at: '2026-11-12T00:00:00Z',
    ocr_text: '<b>untrusted text</b>',
    provenance: {},
    extracted: {},
    details,
    preview_hash: 'a'.repeat(64),
    approval_blockers: ['MISSING_CURRENCY'],
    notices: [],
  }
  assert.deepEqual(decodeReceipt(draft).approval_blockers, ['MISSING_CURRENCY'])
  assert.equal(decodeReceipt(draft).ocr_text, '<b>untrusted text</b>')
  assert.throws(() =>
    decodeReceipt({ ...draft, preview_hash: 'stale-or-malformed' }),
  )
})
test('receipt import rejects unsupported, empty and over-limit images before encoding', () => {
  assert.doesNotThrow(() =>
    validateReceiptImage({ type: 'image/png', size: 5 * 1024 * 1024 }),
  )
  assert.throws(() =>
    validateReceiptImage({ type: 'application/pdf', size: 1000 }),
  )
  assert.throws(() => validateReceiptImage({ type: 'image/jpeg', size: 0 }))
  assert.throws(() =>
    validateReceiptImage({ type: 'image/jpeg', size: 5 * 1024 * 1024 + 1 }),
  )
})
