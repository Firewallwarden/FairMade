import { privateRequest } from './session'
import type { ComparisonRequest, ObservationRequest } from '../types/contracts'
import {
  boolean,
  integer,
  list,
  money,
  nullable,
  object,
  page,
  text,
} from './decode'

function decodeObservation(value: unknown) {
  const data = object(value)
  const details = object(data.details)
  const quantity = object(details.quantity)
  const source = object(details.source)
  return {
    id: text(data.id),
    label: text(details.label),
    price: money(details.price),
    quantity: { value: money(quantity.value), unit: text(quantity.unit) },
    source: {
      name: text(source.name),
      kind: text(source.kind),
      reference: text(source.reference),
    },
    location: text(details.location),
    observed_on: text(details.observed_on),
    quality_notes: nullable(details.quality_notes, text),
  }
}
function decodeReport(value: unknown) {
  const data = object(value)
  const result = object(data.result)
  const quantity = object(result.target_quantity)
  const range = object(result.selected_price_range)
  return {
    id: text(data.id),
    as_of_date: text(data.as_of_date),
    quantity: { value: money(quantity.value), unit: text(quantity.unit) },
    minimum: nullable(range.minimum, money),
    maximum: nullable(range.maximum, money),
    included_count: integer(range.included_count),
    excluded_count: integer(range.excluded_count),
    rows: list(result.rows, (value) => {
      const row = object(value)
      const details = object(row.details)
      const source = object(details.source)
      return {
        id: text(row.observation_id),
        label: text(details.label),
        observed_on: text(details.observed_on),
        source: text(source.name),
        reference: text(source.reference),
        location: text(details.location),
        stale: boolean(row.stale),
        included: boolean(row.included_in_range),
        normalized_price: nullable(row.normalized_price, money),
        exclusion_reasons: list(row.exclusion_reasons, text),
      }
    }),
    warnings: list(result.warnings, text),
  }
}
export const getObservations = (id: string, signal?: AbortSignal) =>
  privateRequest(
    `/products/${id}/price-observations?limit=20&offset=0`,
    page(decodeObservation),
    { signal },
  )
export const createObservation = (id: string, json: ObservationRequest) =>
  privateRequest(`/products/${id}/price-observations`, decodeObservation, {
    method: 'POST',
    json,
  })
export const getComparisons = (id: string, signal?: AbortSignal) =>
  privateRequest(
    `/products/${id}/price-comparisons?limit=20&offset=0`,
    page((value) => {
      const data = object(value)
      return { id: text(data.id), as_of_date: text(data.as_of_date) }
    }),
    { signal },
  )
export const createComparison = (id: string, json: ComparisonRequest) =>
  privateRequest(`/products/${id}/price-comparisons`, decodeReport, {
    method: 'POST',
    json,
  })
export const getComparison = (id: string, report: string) =>
  privateRequest(`/products/${id}/price-comparisons/${report}`, decodeReport)
