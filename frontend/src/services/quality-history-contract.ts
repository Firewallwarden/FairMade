import { boolean, choice, list, money, object, text, timestamp } from './decode.ts'
import { decodeEvaluation, decodeRule } from './quality-contract.ts'
import type { QualityClaim, QualityRule } from './quality-contract.ts'

function decodeClaim(value: unknown): QualityClaim {
  const data = object(value)
  const type = choice(data.type, ['boolean', 'choice', 'numeric'] as const)
  if (type === 'boolean') return { type, value: boolean(data.value) }
  if (type === 'choice') return { type, value: text(data.value) }
  return { type, value: money(data.value), unit: text(data.unit) }
}
export function decodeHistoricalEvaluation(value: unknown) {
  const data = object(value)
  choice(data.evaluation_version, ['quality-evaluation-v1'] as const)
  return {
    ...decodeEvaluation(value),
    created_at: timestamp(data.created_at),
    rules_snapshot: list(data.rules_snapshot, decodeRule),
    claims: Object.fromEntries(Object.entries(object(data.claims)).map(([key, value]) => [key, decodeClaim(value)])),
  }
}
export function matchesCurrentRequirements(saved: { rule_revision: number; rules_snapshot: QualityRule[] }, current: { revision: number; rules: QualityRule[] }) {
  return saved.rule_revision === current.revision && JSON.stringify(saved.rules_snapshot) === JSON.stringify(current.rules)
}
