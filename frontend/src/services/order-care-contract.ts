import {
  boolean,
  choice,
  integer,
  list,
  nullable,
  object,
  text,
  timestamp,
} from './decode.ts'
import { decodePrice } from './catalog-contract.ts'

export function decodeMessage(value: unknown) {
  const data = object(value)
  return {
    id: text(data.id),
    sequence: integer(data.sequence),
    sender: choice(data.sender, ['buyer', 'seller'] as const),
    is_mine: boolean(data.is_mine),
    text: text(data.text),
    created_at: timestamp(data.created_at),
  }
}
export function decodeMessages(value: unknown) {
  const data = object(value)
  return {
    items: list(data.items, decodeMessage),
    next_after_sequence: integer(data.next_after_sequence),
    has_more: boolean(data.has_more),
    notices: list(data.notices, text),
  }
}
export function decodePickup(value: unknown) {
  const data = object(value)
  choice(data.basis, ['seller_reported_unverified'] as const)
  return {
    revision: integer(data.revision),
    state: choice(data.state, [
      'not_started',
      'preparing',
      'ready_for_pickup',
      'collected',
    ] as const),
    pickup_instructions: nullable(data.pickup_instructions, text),
    updates_allowed: boolean(data.updates_allowed),
    notices: list(data.notices, text),
  }
}
export function decodeRefund(value: unknown) {
  const data = object(value)
  choice(data.environment, ['sandbox'] as const)
  return {
    id: text(data.id),
    revision: integer(data.revision),
    state: choice(data.state, [
      'requested',
      'denied',
      'refund_pending',
      'refunded',
      'failed',
      'needs_review',
    ] as const),
    reason: text(data.reason),
    decision: nullable(data.decision, (value) =>
      choice(value, ['approved', 'denied'] as const),
    ),
    decision_reason: nullable(data.decision_reason, text),
    amount: decodePrice(data.amount),
    provider_refund_id: nullable(data.provider_refund_id, text),
    verified_at: nullable(data.verified_at, timestamp),
  }
}
export function isVerifiedRefund(refund: ReturnType<typeof decodeRefund>) {
  return (
    refund.state === 'refunded' &&
    Boolean(refund.provider_refund_id) &&
    Boolean(refund.verified_at)
  )
}
export function decodeOwnReview(value: unknown) {
  const data = object(value)
  return {
    id: text(data.id),
    order_id: text(data.order_id),
    listing_id: text(data.listing_id),
    revision: integer(data.revision),
    state: choice(data.state, ['published', 'withdrawn'] as const),
    rating: integer(data.rating),
    text: text(data.text),
  }
}
export function decodePublicReview(value: unknown) {
  const data = object(value)
  return {
    id: text(data.id),
    rating: integer(data.rating),
    text: text(data.text),
    created_at: timestamp(data.created_at),
    reviewer_label: text(data.reviewer_label),
    claims_basis: text(data.claims_basis),
    purchase_basis: text(data.purchase_basis),
  }
}
