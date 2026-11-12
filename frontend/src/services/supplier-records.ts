import { privateRequest } from './session'
import {
  boolean,
  choice,
  integer,
  list,
  money,
  nullable,
  object,
  page,
  text,
  timestamp,
} from './decode'
export type SupplierFields = {
  name: string
  location: string | null
  notes: string | null
  archived: boolean
}
export type SupplierExperienceInput = {
  request_id: string
  expected_supplier_revision: number
  label: string
  observed_on: string
  rating: number | null
  promised_on: string | null
  received_on: string | null
  notes: string | null
  source_quote_id: string | null
  corrects_experience_id: string | null
  correction_reason: string | null
}
function decodeSupplier(value: unknown) {
  const data = object(value)
  choice(data.basis, ['seller_reported_unverified'] as const)
  return {
    id: text(data.id),
    name: text(data.name),
    location: nullable(data.location, text),
    notes: nullable(data.notes, text),
    archived: boolean(data.archived),
    revision: integer(data.revision),
  }
}
function decodeSupplierEvent(value: unknown) {
  const data = object(value)
  return {
    supplier_id: text(data.supplier_id),
    revision: integer(data.revision),
    reason: text(data.reason),
    before: nullable(data.before, object),
    after: object(data.after),
    created_at: timestamp(data.created_at),
  }
}
function decodeExperience(value: unknown) {
  const data = object(value)
  choice(data.basis, ['seller_reported_unverified'] as const)
  return {
    id: text(data.id),
    label: text(data.label),
    observed_on: text(data.observed_on),
    rating: nullable(data.rating, integer),
    promised_on: nullable(data.promised_on, text),
    received_on: nullable(data.received_on, text),
    corrects_experience_id: nullable(data.corrects_experience_id, text),
    source_quote_id: nullable(data.source_quote_id, text),
  }
}
export const getSupplierProfiles = (
  offset: number,
  archived: 'all' | 'active' | 'archived',
  signal?: AbortSignal,
) =>
  privateRequest(
    `/seller/suppliers?limit=20&offset=${offset}${archived === 'all' ? '' : `&archived=${archived === 'archived'}`}`,
    page(decodeSupplier),
    { signal },
  )
export const getSupplierProfile = (id: string, signal?: AbortSignal) =>
  privateRequest(`/seller/suppliers/${id}`, decodeSupplier, { signal })
export const createSupplierProfile = (
  request: SupplierFields & { request_id: string },
) =>
  privateRequest('/seller/suppliers', decodeSupplierEvent, {
    method: 'POST',
    json: request,
  })
export const updateSupplierProfile = (
  id: string,
  request: SupplierFields & {
    request_id: string
    expected_revision: number
    reason: string
  },
) =>
  privateRequest(`/seller/suppliers/${id}`, decodeSupplierEvent, {
    method: 'PUT',
    json: request,
  })
export const getSupplierHistory = (
  id: string,
  offset: number,
  signal?: AbortSignal,
) =>
  privateRequest(
    `/seller/suppliers/${id}/history?limit=20&offset=${offset}`,
    page(decodeSupplierEvent),
    { signal },
  )
export const getSupplierExperiences = (
  id: string,
  offset: number,
  query: string,
  signal?: AbortSignal,
) =>
  privateRequest(
    `/seller/suppliers/${id}/experiences?limit=20&offset=${offset}&${query}`,
    page(decodeExperience),
    { signal },
  )
export const recordSupplierExperience = (
  id: string,
  request: SupplierExperienceInput,
) =>
  privateRequest(`/seller/suppliers/${id}/experiences`, decodeExperience, {
    method: 'POST',
    json: request,
  })
export const getSupplierExperience = (id: string, experience: string) =>
  privateRequest(
    `/seller/suppliers/${id}/experiences/${experience}`,
    (value) => {
      const data = object(value)
      return {
        ...decodeExperience(value),
        request: object(data.request),
        supplier_snapshot: object(data.supplier_snapshot),
        quote_snapshot: nullable(data.quote_snapshot, object),
      }
    },
  )
export const getSupplierReliability = (
  id: string,
  query: string,
  signal?: AbortSignal,
) =>
  privateRequest(
    `/seller/suppliers/${id}/reliability?${query}`,
    (value) => {
      const data = object(value)
      choice(data.basis, ['seller_reported_unverified'] as const)
      return {
        experiences_count: integer(data.experiences_count),
        rated_count: integer(data.rated_count),
        average_rating: nullable(data.average_rating, money),
        dated_deliveries_count: integer(data.dated_deliveries_count),
        on_time_count: integer(data.on_time_count),
        late_count: integer(data.late_count),
        unknown_delivery_count: integer(data.unknown_delivery_count),
        notices: list(data.notices, text),
        observed_from: nullable(data.observed_from, text),
        observed_until: nullable(data.observed_until, text),
      }
    },
    { signal },
  )
