import {
  boolean,
  choice,
  integer,
  list,
  nullable,
  object,
  text,
} from './decode.ts'
import { decodeDetail, decodePrice } from './catalog-contract.ts'
import { decodeCart } from './order-contract.ts'
import type { CartRequest } from './order-contract.ts'
export type PlanAlternative = {
  listing_id: string
  expected_listing_revision: number
}
export type BasketNeed = {
  group_id: string
  quantity: number
  alternatives: PlanAlternative[]
}
export type BasketRequest = {
  storefront_id: string
  budget: string | null
  needs: BasketNeed[]
}
export type BundleRequest = {
  storefront_id: string
  candidates: PlanAlternative[]
  budget: string | null
  limit: number
}
function decodePlanCart(value: unknown): CartRequest {
  const data = object(value)
  return {
    items: list(data.items, (value) => {
      const item = object(value)
      return {
        listing_id: text(item.listing_id),
        expected_listing_revision: integer(item.expected_listing_revision),
        quantity: integer(item.quantity),
      }
    }),
  }
}
function decodeCandidate(value: unknown) {
  const data = object(value)
  return {
    listing_id: text(data.listing_id),
    eligible: boolean(data.eligible),
    exclusions: list(data.exclusions, text),
    affinity_reasons: list(data.affinity_reasons, text),
  }
}
export function decodeBasket(value: unknown) {
  const data = object(value)
  choice(data.optimization_version, ['single-storefront-basket-v1'] as const)
  return {
    status: choice(data.status, [
      'ready',
      'over_budget',
      'unavailable',
    ] as const),
    minimum_subtotal: nullable(data.minimum_subtotal, decodePrice),
    remaining_budget: nullable(data.remaining_budget, decodePrice),
    personalized: boolean(data.personalized),
    cart: nullable(data.cart, decodePlanCart),
    preview: nullable(data.preview, decodeCart),
    notices: list(data.notices, text),
    needs: list(data.needs, (value) => {
      const need = object(value)
      return {
        group_id: text(need.group_id),
        quantity: integer(need.quantity),
        chosen_listing_id: nullable(need.chosen_listing_id, text),
        candidates: list(need.candidates, decodeCandidate),
      }
    }),
  }
}
export function decodeBundles(value: unknown) {
  const data = object(value)
  choice(data.bundle_version, ['same-storefront-pairs-v1'] as const)
  return {
    role: choice(data.role, ['buyer', 'seller'] as const),
    eligible_pairs: integer(data.eligible_pairs),
    budget_excluded_pairs: integer(data.budget_excluded_pairs),
    notices: list(data.notices, text),
    candidates: list(data.candidates, decodeCandidate),
    suggestions: list(data.suggestions, (value) => {
      const row = object(value)
      return {
        listings: list(row.listings, decodeDetail),
        subtotal: decodePrice(row.subtotal),
        reasons: list(row.reasons, text),
        observed_copurchase_orders: nullable(
          row.observed_copurchase_orders,
          integer,
        ),
        cart: nullable(row.cart, decodePlanCart),
      }
    }),
  }
}
