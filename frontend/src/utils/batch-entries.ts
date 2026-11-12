import type { BatchCost, LaborCost } from '../types/pricing.ts'
import { costCategories } from '../types/pricing.ts'
import { choice } from '../services/decode.ts'
import { fieldValue } from './form.ts'
export function readBatchEntries(
  fields: FormData,
  prefix: string,
): { costs: BatchCost[]; labor: LaborCost[] } {
  return {
    costs: fields
      .getAll(`${prefix}-cost-row`)
      .map(String)
      .map((key) => ({
        label: fieldValue(fields, `${prefix}-cost-label-${key}`),
        category: choice(
          fieldValue(fields, `${prefix}-cost-category-${key}`),
          costCategories,
        ),
        amount: fieldValue(fields, `${prefix}-cost-amount-${key}`),
      })),
    labor: fields
      .getAll(`${prefix}-labor-row`)
      .map(String)
      .map((key) => ({
        label: fieldValue(fields, `${prefix}-labor-label-${key}`),
        hours: fieldValue(fields, `${prefix}-labor-hours-${key}`),
        hourly_rate: fieldValue(fields, `${prefix}-labor-rate-${key}`),
      })),
  }
}
export function rateAsPercent(rate: string) {
  if (!/^\d+(\.\d{1,6})?$/.test(rate))
    throw new Error('Unsupported saved fractional rate.')
  const [whole, fraction = ''] = rate.split('.')
  const digits = (BigInt(whole + fraction) * 100n)
    .toString()
    .padStart(fraction.length + 1, '0')
  if (!fraction.length) return digits
  const wholePercent = digits.slice(0, -fraction.length)
  const fractionalPercent = digits.slice(-fraction.length).replace(/0+$/, '')
  return fractionalPercent
    ? `${wholePercent}.${fractionalPercent}`
    : wholePercent
}
