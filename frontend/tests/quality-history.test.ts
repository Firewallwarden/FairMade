import assert from 'node:assert/strict'
import { test } from 'node:test'
import { matchesCurrentRequirements } from '../src/services/quality-history-contract.ts'
const rules = [{ key: 'organic', label: 'Organic', type: 'boolean' as const, expected: true }]
test('historical requirements need both revision and captured rules to match', () => {
  const saved = { rule_revision: 2, rules_snapshot: rules }
  assert.equal(matchesCurrentRequirements(saved, { revision: 2, rules }), true)
  assert.equal(matchesCurrentRequirements(saved, { revision: 3, rules }), false)
  assert.equal(matchesCurrentRequirements(saved, { revision: 2, rules: [{ ...rules[0], expected: false }] }), false)
})
