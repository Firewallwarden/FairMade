import assert from 'node:assert/strict'
import { test } from 'node:test'
import { decodeSupplierReport } from '../src/services/supplier-contract.ts'

const row = (eligible: boolean, status: string, reasons: string[]) => ({
  quote_id: 'synthetic-quote',
  details: { supplier_name: 'Synthetic supplier', observed_on: '2026-11-11' },
  eligible_for_cost_comparison: eligible,
  quality: { status },
  exclusion_reasons: reasons,
  cost: {
    purchase_cost: '2.00',
    cost_per_usable_unit: '1.00',
    packages_to_buy: 2,
    transport_cost: '0.00',
  },
})
const report = (entry: unknown) => ({
  id: 'synthetic-report',
  result: {
    rule_revision: 1,
    as_of_date: '2026-11-11',
    required_quantity: { value: '2', unit: 'kg' },
    eligible_count: 0,
    lowest_purchase_cost: null,
    warnings: [],
    rows: [entry],
  },
})

test('failed supplier requirements remain excluded even when a low cost is available', () => {
  const decoded = decodeSupplierReport(
    report(row(false, 'failed', ['quality_lock_failed'])),
  )
  assert.equal(decoded.rows[0].eligible, false)
  assert.equal(decoded.rows[0].cost?.purchase_cost, '2.00')
  assert.equal(decoded.lowest_purchase_cost, null)
})

test('contradictory eligibility cannot display a failed or otherwise excluded quote as a saving', () => {
  assert.throws(() => decodeSupplierReport(report(row(true, 'failed', []))))
  assert.throws(() =>
    decodeSupplierReport(report(row(true, 'passed', ['transport_unknown']))),
  )
})
