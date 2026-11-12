import { privateRequest } from './session'
import { choice } from './decode'
import { productTypes } from '../types/contracts'
import type {
  EvaluationRequest,
  ListingRequest,
  PassportRequest,
  ProductType,
  Quantity,
} from '../types/contracts'
import {
  empty,
  integer,
  list,
  nullable,
  object,
  page,
  text,
  timestamp,
} from './decode'
import { decodePricing } from './pricing-contract'
import { decodeEvaluation, decodeLocks } from './quality-contract'
import type { QualityRule } from './quality-contract'
import { decodeCatalogContent, decodePassport } from './catalog-contract'
import type { PricingRequest } from '../types/pricing'
import { ApiError } from './http'
import { decodeEditablePassport } from './passport-contract'

export function decodeProduct(value: unknown) {
  const data = object(value)
  return {
    id: text(data.id),
    name: text(data.name),
    product_type: choice(data.product_type, productTypes),
    selling_unit: text(data.selling_unit),
    description: nullable(data.description, text),
  }
}
export type SellerProduct = ReturnType<typeof decodeProduct>

function decodeAnalysisSummary(value: unknown) {
  const data = object(value)
  return {
    id: text(data.id),
    created_at: timestamp(data.created_at),
    calculation_version: text(data.calculation_version),
  }
}
function decodeAnalysis(value: unknown) {
  const data = object(value)
  return {
    ...decodeAnalysisSummary(value),
    result: decodePricing(data.result),
    product_snapshot: decodeProduct(data.product_snapshot),
  }
}
function decodeInventory(value: unknown) {
  const data = object(value)
  return {
    revision: integer(data.revision),
    on_hand: integer(data.on_hand),
    reserved: integer(data.reserved),
    available: integer(data.available),
  }
}
function decodeDraft(value: unknown) {
  const data = object(value)
  return { id: text(data.id), revision: integer(data.revision) }
}
function decodeReview(value: unknown) {
  const data = object(value)
  const result = object(data.result)
  return {
    id: text(data.id),
    explanations: list(result.explanations, (value) =>
      text(object(value).message),
    ),
    warnings: list(result.warnings, text),
  }
}
function decodeListing(value: unknown) {
  const data = object(value)
  const content = object(data.content)
  return {
    id: text(data.id),
    revision: integer(data.revision),
    state: text(data.state),
    content: {
      passport_publication_id: text(content.passport_publication_id),
      seller_display_name: text(content.seller_display_name),
      location: nullable(content.location, text),
      summary: nullable(content.summary, text),
      photos: nullable(content.photos, (value) =>
        list(value, (value) => {
          const photo = object(value)
          return {
            photo_id: text(photo.photo_id),
            alt_text: text(photo.alt_text),
          }
        }),
      ),
      selling_quantity: nullable(content.selling_quantity, (value) => {
        const quantity = object(value)
        return { value: text(quantity.value), unit: text(quantity.unit) }
      }),
    },
  }
}
async function optional<T>(promise: Promise<T>): Promise<T | null> {
  try {
    return await promise
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}

export const getProducts = (offset: number, signal?: AbortSignal) =>
  privateRequest(`/products?limit=20&offset=${offset}`, page(decodeProduct), {
    signal,
  })
export const createProduct = (json: {
  name: string
  product_type: ProductType
  selling_unit: string
  description: string | null
}) => privateRequest('/products', decodeProduct, { method: 'POST', json })
export const getProduct = (id: string, signal?: AbortSignal) =>
  privateRequest(`/products/${id}`, decodeProduct, { signal })
export const updateProduct = (
  id: string,
  json: { name: string; selling_unit: string; description: string | null },
) => privateRequest(`/products/${id}`, decodeProduct, { method: 'PATCH', json })
export const getAnalyses = (id: string, signal?: AbortSignal) =>
  privateRequest(
    `/products/${id}/analyses?limit=100`,
    page(decodeAnalysisSummary),
    { signal },
  )
export const getAnalysis = (
  id: string,
  analysisId: string,
  signal?: AbortSignal,
) =>
  privateRequest(`/products/${id}/analyses/${analysisId}`, decodeAnalysis, {
    signal,
  })
export const saveAnalysis = (
  id: string,
  json: PricingRequest,
  signal?: AbortSignal,
) =>
  privateRequest(`/products/${id}/analyses`, decodeAnalysis, {
    method: 'POST',
    json,
    signal,
  })
export const getLocks = (id: string, signal?: AbortSignal) =>
  privateRequest(`/products/${id}/quality-locks`, decodeLocks, { signal })
export const saveLocks = (id: string, revision: number, rules: QualityRule[]) =>
  privateRequest(`/products/${id}/quality-locks`, decodeLocks, {
    method: 'PUT',
    json: { expected_revision: revision, rules },
  })
export const evaluateQuality = (id: string, json: EvaluationRequest) =>
  privateRequest(`/products/${id}/quality-evaluations`, decodeEvaluation, {
    method: 'POST',
    json,
  })
export const getEvaluations = (id: string, signal?: AbortSignal) =>
  privateRequest(
    `/products/${id}/quality-evaluations?limit=100`,
    page((value) => {
      const data = object(value)
      return {
        id: text(data.id),
        candidate_label: text(data.candidate_label),
        status: text(data.status),
        rule_revision: integer(data.rule_revision),
      }
    }),
    { signal },
  )
export const createReview = (
  id: string,
  analysis: string,
  evaluations: string[],
  comparison: string | null = null,
  quantity?: Quantity,
) =>
  privateRequest(`/products/${id}/pricing-reviews`, decodeReview, {
    method: 'POST',
    json: {
      pricing_analysis_id: analysis,
      quality_evaluation_ids: evaluations,
      comparison_report_id: comparison,
      ...(quantity && { production_unit_quantity: quantity }),
    },
  })
export const getInventory = (id: string, signal?: AbortSignal) =>
  privateRequest(`/products/${id}/inventory`, decodeInventory, { signal })
export const saveInventory = (
  id: string,
  revision: number,
  sellingUnit: string,
  count: number,
) =>
  privateRequest(`/products/${id}/inventory`, decodeInventory, {
    method: 'PUT',
    json: {
      expected_revision: revision,
      selling_unit: sellingUnit,
      on_hand: count,
    },
  })
export const createPassport = (id: string, json: PassportRequest) =>
  privateRequest(`/products/${id}/passports`, decodeDraft, {
    method: 'POST',
    json,
  })
export const getPassportDraft = (id: string, draft: string) =>
  privateRequest(`/products/${id}/passports/${draft}`, decodeEditablePassport)
export const updatePassportDraft = (id: string, draft: string, revision: number, json: PassportRequest) =>
  privateRequest(`/products/${id}/passports/${draft}`, decodeEditablePassport, {
    method: 'PUT',
    json: { ...json, expected_revision: revision },
  })
export const getPassportDrafts = (id: string, signal?: AbortSignal) =>
  privateRequest(`/products/${id}/passports?limit=100`, page(decodeDraft), {
    signal,
  })
export const getPublications = (id: string, draft: string) =>
  privateRequest(
    `/products/${id}/passports/${draft}/publications?limit=100`,
    page((value) => {
      const data = object(value)
      return {
        id: text(data.id),
        state: text(data.state),
        revision: integer(data.draft_revision),
        payload: decodePassport(data.payload),
      }
    }),
  )
export const getPassportPreview = (id: string, draft: string) =>
  privateRequest(`/products/${id}/passports/${draft}/preview`, (value) => {
    const data = object(value)
    return {
      revision: integer(data.revision),
      preview_hash: text(data.preview_hash),
      payload: decodePassport(data.payload),
    }
  })
export const publishPassport = (
  id: string,
  draft: string,
  revision: number,
  hash: string,
) =>
  privateRequest(
    `/products/${id}/passports/${draft}/publish`,
    (value) => ({ id: text(object(value).id) }),
    {
      method: 'POST',
      json: { expected_revision: revision, preview_hash: hash, approved: true },
    },
  )
export const getListing = (id: string, signal?: AbortSignal) =>
  optional(privateRequest(`/products/${id}/listing`, decodeListing, { signal }))
export const saveListing = (
  id: string,
  json: ListingRequest,
  revision?: number,
) =>
  privateRequest(`/products/${id}/listing`, decodeListing, {
    method: revision ? 'PUT' : 'POST',
    json,
  })
export const getListingPreview = (id: string) =>
  privateRequest(`/products/${id}/listing/preview`, (value) => {
    const data = object(value)
    return {
      revision: integer(data.revision),
      preview_hash: text(data.preview_hash),
      payload: decodeCatalogContent(data.payload),
      publication_blockers: list(data.publication_blockers, text),
    }
  })
export const activateListing = (id: string, revision: number, hash: string) =>
  privateRequest(`/products/${id}/listing/activate`, decodeListing, {
    method: 'POST',
    json: { expected_revision: revision, preview_hash: hash, approved: true },
  })
export const deactivateListing = (id: string) =>
  privateRequest(`/products/${id}/listing/deactivate`, empty, {
    method: 'POST',
  })
