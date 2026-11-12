import { choice } from '../services/decode.ts'
import type { QualityClaim, QualityRule } from '../services/quality-contract.ts'
import { fieldValue } from './form.ts'
export function readOptionalPreferences(
  fields: FormData,
  prefix: string,
): QualityRule[] {
  const rows = fields.getAll(`${prefix}-row`).map(String)
  if (rows.length > 8)
    throw new Error('Choose no more than eight optional preferences.')
  const seen = new Set<string>()
  return rows.map((row) => {
    const key = fieldValue(fields, `${prefix}-key-${row}`),
      label = fieldValue(fields, `${prefix}-label-${row}`)
    if (!/^[a-z][a-z0-9_]{0,63}$/.test(key) || seen.has(key))
      throw new Error('Optional preference keys must be valid and distinct.')
    seen.add(key)
    const type = choice(fieldValue(fields, `${prefix}-type-${row}`), [
      'boolean',
      'choice',
      'numeric',
    ] as const)
    if (type === 'boolean')
      return {
        key,
        label,
        type,
        expected:
          choice(fieldValue(fields, `${prefix}-expected-${row}`), [
            'true',
            'false',
          ] as const) === 'true',
      }
    if (type === 'choice') {
      const allowed_values = fieldValue(fields, `${prefix}-choices-${row}`)
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean)
      if (
        !allowed_values.length ||
        allowed_values.length > 100 ||
        new Set(allowed_values).size !== allowed_values.length
      )
        throw new Error('Choose 1–100 distinct optional text values.')
      return { key, label, type, allowed_values }
    }
    const minimum = fieldValue(fields, `${prefix}-minimum-${row}`) || null,
      maximum = fieldValue(fields, `${prefix}-maximum-${row}`) || null
    if (minimum === null && maximum === null)
      throw new Error('Choose at least one bound for a numeric preference.')
    return {
      key,
      label,
      type,
      minimum,
      maximum,
      unit: fieldValue(fields, `${prefix}-unit-${row}`),
    }
  })
}
export function readAdditionalClaims(
  fields: FormData,
  existing: Record<string, QualityClaim>,
  reservedKeys: readonly string[] = Object.keys(existing),
): Record<string, QualityClaim> {
  const claims = { ...existing },
    rows = fields.getAll('quote-extra-row').map(String)
  if (rows.length > 8)
    throw new Error('Add no more than eight extra reported claims.')
  for (const row of rows) {
    const key = fieldValue(fields, `quote-extra-key-${row}`)
    if (
      !/^[a-z][a-z0-9_]{0,63}$/.test(key) ||
      Object.hasOwn(claims, key) ||
      reservedKeys.includes(key)
    )
      throw new Error(
        'Extra claim keys must be distinct and cannot replace a mandatory requirement’s claim.',
      )
    const type = choice(fieldValue(fields, `quote-extra-type-${row}`), [
        'boolean',
        'choice',
        'numeric',
      ] as const),
      value = fieldValue(fields, `quote-extra-value-${row}`)
    claims[key] =
      type === 'boolean'
        ? { type, value: choice(value, ['true', 'false'] as const) === 'true' }
        : type === 'choice'
          ? { type, value }
          : { type, value, unit: fieldValue(fields, `quote-extra-unit-${row}`) }
  }
  if (Object.keys(claims).length > 100)
    throw new Error('A quote may contain at most 100 total claims.')
  return claims
}
