import type { QualityRule } from '../services/quality-contract'

// Backend strings remain authoritative; Number is used only for display.
export const usd = (amount: string) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 6,
  }).format(Number(amount))

export function ruleDescription(rule: QualityRule) {
  if (rule.type === 'boolean')
    return rule.expected ? 'Must be true' : 'Must be false'
  if (rule.type === 'choice')
    return `Allowed: ${rule.allowed_values.join(', ')}`
  return `${rule.minimum === null ? 'No minimum' : 'Minimum ' + rule.minimum}; ${rule.maximum === null ? 'no maximum' : 'maximum ' + rule.maximum} ${rule.unit}`
}
