import { privateRequest } from './session'
import { choice, list, object, page, text, timestamp } from './decode'
import { decodePricing } from './pricing-contract'

function decodeSummary(value: unknown) {
  const data = object(value)
  choice(data.review_version, ['seller-pricing-review-v1'] as const)
  return { id: text(data.id), created_at: timestamp(data.created_at), reviewed_on: text(data.reviewed_on) }
}
export const getReviewHistory = (id: string, offset: number, signal?: AbortSignal) =>
  privateRequest(`/products/${id}/pricing-reviews?limit=20&offset=${offset}`, page(decodeSummary), { signal })
export const getSavedReview = (id: string, review: string, signal?: AbortSignal) =>
  privateRequest(`/products/${id}/pricing-reviews/${review}`, value => {
    const data = object(value)
    choice(data.basis, ['seller_reported_unverified'] as const)
    const result = object(data.result)
    const evidence = object(data.evidence_snapshot)
    const analysis = object(evidence.pricing_analysis)
    const product = object(analysis.product_snapshot)
    return {
      ...decodeSummary(data), unit: text(product.selling_unit),
      economics: decodePricing(result.economics), quality: object(result.quality), market: object(result.market_context),
      explanations: list(result.explanations, value => {
        const item = object(value)
        return { code: text(item.code), message: text(item.message) }
      }), warnings: list(result.warnings, text),
      evidence, request: object(data.request_snapshot),
    }
  }, { signal })
