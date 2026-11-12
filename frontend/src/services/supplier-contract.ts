import {
  boolean,
  integer,
  list,
  money,
  nullable,
  object,
  text,
} from './decode.ts'
import { decodeRule } from './quality-contract.ts'

export const supplyUnits = ['g', 'kg', 'ml', 'l', 'item'] as const
export function decodeSourcingInput(value: unknown) {
  const data = object(value)
  return {
    id: text(data.id),
    label: text(data.label),
    rule_revision: integer(data.rule_revision),
    rules: list(data.rules, decodeRule),
  }
}
export function decodeQuote(value: unknown) {
  const data = object(value)
  const details = object(data.details)
  const source = object(details.source)
  const quantity = object(details.package_quantity)
  return {
    id: text(data.id),
    supplier_name: text(details.supplier_name),
    price: money(details.package_price),
    quantity: { value: money(quantity.value), unit: text(quantity.unit) },
    observed_on: text(details.observed_on),
    availability: text(details.availability),
    location: text(details.location),
    source: { name: text(source.name), reference: text(source.reference) },
  }
}
export function decodeSupplierReport(value: unknown) {
  const data = object(value)
  const result = object(data.result)
  const quantity = object(result.required_quantity)
  return {
    id: text(data.id),
    rule_revision: integer(result.rule_revision),
    as_of_date: text(result.as_of_date),
    quantity: { value: money(quantity.value), unit: text(quantity.unit) },
    eligible_count: integer(result.eligible_count),
    lowest_purchase_cost: nullable(result.lowest_purchase_cost, money),
    warnings: list(result.warnings, text),
    rows: list(result.rows, (value) => {
      const row = object(value)
      const details = object(row.details)
      const quality = object(row.quality)
      const reasons = list(row.exclusion_reasons, text)
      const eligible = boolean(row.eligible_for_cost_comparison)
      if (eligible && (quality.status !== 'passed' || reasons.length))
        throw new Error('Conflicting supplier eligibility')
      return {
        supplier_name: text(details.supplier_name),
        quote_id: text(row.quote_id),
        observed_on: text(details.observed_on),
        eligible,
        quality: text(quality.status),
        reasons,
        cost: nullable(row.cost, (value) => {
          const cost = object(value)
          return {
            purchase_cost: money(cost.purchase_cost),
            unit_cost: money(cost.cost_per_usable_unit),
            packages: integer(cost.packages_to_buy),
            transport: money(cost.transport_cost),
          }
        }),
      }
    }),
  }
}
