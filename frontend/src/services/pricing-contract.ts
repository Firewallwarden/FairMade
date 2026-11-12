import { costCategories } from '../types/pricing.ts'
import type { PricingResponse } from '../types/pricing.ts'

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Expected object')
  return value as Record<string, unknown>
}

function decimal(value: unknown): string {
  if (typeof value !== 'string' || !/^-?\d+(\.\d+)?$/.test(value) || !Number.isFinite(Number(value))) throw new Error('Expected decimal string')
  return value
}

function string(value: unknown): string {
  if (typeof value !== 'string') throw new Error('Expected string')
  return value
}

function boolean(value: unknown): boolean {
  if (typeof value !== 'boolean') throw new Error('Expected boolean')
  return value
}

function array(value: unknown): unknown[] {
  if (!Array.isArray(value)) throw new Error('Expected array')
  return value
}

export function decodePricing(value: unknown): PricingResponse {
  const data = record(value)
  if (data.currency !== 'USD' || data.basis !== 'seller_supplied_unverified' || data.calculation_version !== 'production-economics-v1') throw new Error('Unsupported contract')
  const costs = record(data.costs)
  const totals = record(costs.category_totals)
  const range = record(data.sustainable_price_range)
  const categoryTotals: PricingResponse['costs']['category_totals'] = {}
  for (const category of costCategories) {
    if (category in totals) categoryTotals[category] = decimal(totals[category])
  }
  return {
    currency: data.currency, basis: data.basis, calculation_version: data.calculation_version,
    costs: { category_totals: categoryTotals, labor_total: decimal(costs.labor_total), batch_total: decimal(costs.batch_total), unit_cost: decimal(costs.unit_cost) },
    fixed_fee_per_unit: decimal(data.fixed_fee_per_unit), break_even_price: decimal(data.break_even_price),
    sustainable_price_range: { minimum: decimal(range.minimum), maximum: decimal(range.maximum) },
    scenarios: array(data.scenarios).map((value) => {
      const item = record(value)
      return { price: decimal(item.price), processing_fee_per_unit: decimal(item.processing_fee_per_unit), profit_per_unit: decimal(item.profit_per_unit), batch_profit: decimal(item.batch_profit), margin: item.margin === null ? null : decimal(item.margin), markup: item.markup === null ? null : decimal(item.markup), below_break_even: boolean(item.below_break_even), below_target_margin: boolean(item.below_target_margin) }
    }),
    warnings: array(data.warnings).map((value) => { const item = record(value); return { code: string(item.code), message: string(item.message) } }),
    assumptions: array(data.assumptions).map(string),
  }
}

// Move the decimal point exactly; do not use floating-point arithmetic for rates.
export function percentToRate(percent: string): string {
  if (!/^\d{1,2}(\.\d{1,4})?$/.test(percent)) throw new Error('Enter a percentage from 0 to less than 100, with up to four decimal places.')
  const [whole, fraction = ''] = percent.split('.')
  return `0.${whole.padStart(2, '0')}${fraction}`.replace(/0+$/, '').replace(/\.$/, '')
}
