import {
  boolean,
  choice,
  integer,
  list,
  money,
  nullable,
  object,
  text,
} from './decode.ts'

export type QualityRule =
  | { key: string; label: string; type: 'boolean'; expected: boolean }
  | { key: string; label: string; type: 'choice'; allowed_values: string[] }
  | {
      key: string
      label: string
      type: 'numeric'
      minimum: string | null
      maximum: string | null
      unit: string
    }

export type QualityClaim =
  | { type: 'boolean'; value: boolean }
  | { type: 'choice'; value: string }
  | { type: 'numeric'; value: string; unit: string }

export function decodeRule(value: unknown): QualityRule {
  const data = object(value)
  const base = { key: text(data.key), label: text(data.label) }
  const type = choice(data.type, ['boolean', 'choice', 'numeric'] as const)
  if (type === 'boolean')
    return { ...base, type, expected: boolean(data.expected) }
  if (type === 'choice')
    return { ...base, type, allowed_values: list(data.allowed_values, text) }
  return {
    ...base,
    type,
    minimum: nullable(data.minimum, money),
    maximum: nullable(data.maximum, money),
    unit: text(data.unit),
  }
}

export function decodeLocks(value: unknown) {
  const data = object(value)
  return {
    revision: integer(data.revision),
    rules: list(data.rules, decodeRule),
  }
}

export function decodeEvaluation(value: unknown) {
  const data = object(value)
  return {
    id: text(data.id),
    candidate_label: text(data.candidate_label),
    rule_revision: integer(data.rule_revision),
    status: choice(data.status, [
      'passed',
      'failed',
      'unknown',
      'not_evaluated',
    ] as const),
    checks: list(data.checks, (value) => {
      const check = object(value)
      return {
        key: text(check.key),
        label: text(check.label),
        status: text(check.status),
        message: text(check.message),
      }
    }),
  }
}
