import { privateRequest } from './session'
import { object, page, text, list, nullable, money, boolean } from './decode'
import {
  decodeSourcingInput,
  decodeQuote,
  decodeSupplierReport,
  supplyUnits,
} from './supplier-contract'
import type { QualityRule, QualityClaim } from './quality-contract'
import type { sourceKinds } from '../types/contracts'

export type SupplyQuantity = {
  value: string
  unit: (typeof supplyUnits)[number]
}
export type QuoteRequest = {
  supplier_name: string
  source: {
    name: string
    kind: (typeof sourceKinds)[number]
    reference: string
  }
  location: string
  observed_on: string
  valid_until: string | null
  currency: 'USD'
  package_price: string
  package_quantity: SupplyQuantity
  usable_fraction: string
  minimum_packages: number
  maximum_packages: number | null
  transport_cost: string | null
  availability: 'available' | 'unavailable' | 'unknown'
  claims: Record<string, QualityClaim>
  notes: string | null
}
const base = (product: string) =>
  `/products/${product}/sourcing-inputs` as const
export const getSourcingInputs = (product: string, signal?: AbortSignal) =>
  privateRequest(`${base(product)}?limit=100`, page(decodeSourcingInput), {
    signal,
  })
export const createSourcingInput = (product: string, label: string) =>
  privateRequest(base(product), decodeSourcingInput, {
    method: 'POST',
    json: { label },
  })
export const saveInputLocks = (
  product: string,
  input: string,
  revision: number,
  rules: QualityRule[],
) =>
  privateRequest(
    `${base(product)}/${input}/quality-locks`,
    decodeSourcingInput,
    { method: 'PUT', json: { expected_revision: revision, rules } },
  )
export const getSupplierQuotes = (
  product: string,
  input: string,
  signal?: AbortSignal,
) =>
  privateRequest(
    `${base(product)}/${input}/supplier-quotes?limit=100`,
    page(decodeQuote),
    { signal },
  )
export const createSupplierQuote = (
  product: string,
  input: string,
  json: QuoteRequest,
) =>
  privateRequest(`${base(product)}/${input}/supplier-quotes`, decodeQuote, {
    method: 'POST',
    json,
  })
export const getSupplierReports = (
  product: string,
  input: string,
  signal?: AbortSignal,
) =>
  privateRequest(
    `${base(product)}/${input}/supplier-comparisons?limit=100`,
    page((value) => {
      const data = object(value)
      return { id: text(data.id), as_of_date: text(data.as_of_date) }
    }),
    { signal },
  )
export const createSupplierReport = (
  product: string,
  input: string,
  request: {
    quote_ids: string[]
    expected_rule_revision: number
    required_quantity: SupplyQuantity
    max_age_days: number
  },
) =>
  privateRequest(
    `${base(product)}/${input}/supplier-comparisons`,
    decodeSupplierReport,
    { method: 'POST', json: request },
  )
export const getSupplierReport = (product: string, input: string, id: string) =>
  privateRequest(
    `${base(product)}/${input}/supplier-comparisons/${id}`,
    decodeSupplierReport,
  )
export const getSupplierRecommendations = (
  product: string,
  report: string,
  mode: 'savings' | 'quality' | 'balanced',
  objective: 'purchase_outlay' | 'usable_unit',
  preferences: QualityRule[] = [],
) =>
  privateRequest(
    `/products/${product}/supplier-recommendations`,
    (value) => {
      const data = object(value)
      return {
        notices: list(data.notices, text),
        rows: list(data.rows, (value) => {
          const row = object(value)
          return {
            supplier_name: text(row.supplier_name),
            eligible: boolean(row.eligible),
            reason: text(row.selection_reason),
            exclusions: list(row.exclusion_reasons, text),
            objective_cost: nullable(row.objective_cost, money),
            preference_checks: list(row.preference_checks, (value) => {
              const check = object(value)
              return {
                label: text(check.label),
                status: text(check.status),
                message: text(check.message),
              }
            }),
          }
        }),
      }
    },
    {
      method: 'POST',
      json: {
        supplier_report_id: report,
        mode,
        cost_objective: objective,
        preferences,
      },
    },
  )
