import { apiRequest } from './api'
import { decodePricing } from './pricing-contract'
import type { PricingRequest } from '../types/pricing'

export function analyzePricing(input: PricingRequest, signal?: AbortSignal) {
  return apiRequest('/pricing/analyze', decodePricing, { method: 'POST', json: input, signal })
}
