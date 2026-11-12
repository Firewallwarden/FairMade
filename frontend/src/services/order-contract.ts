import {
  choice,
  integer,
  list,
  nullable,
  object,
  text,
  timestamp,
} from './decode.ts'
import { decodeCatalogContent, decodePrice } from './catalog-contract.ts'

export type CartRequest = {
  items: {
    listing_id: string
    expected_listing_revision: number
    quantity: number
  }[]
}

export function decodeCart(value: unknown) {
  const data = object(value)
  choice(data.order_version, ['unpaid-order-v1'] as const)
  return {
    items: list(data.items, (value) => {
      const item = object(value)
      return {
        listing_id: text(item.listing_id),
        published_revision: integer(item.published_revision),
        quantity: integer(item.quantity),
        unit_price: decodePrice(item.unit_price),
        subtotal: decodePrice(item.subtotal),
        listing: decodeCatalogContent(item.listing),
      }
    }),
    subtotal: decodePrice(data.subtotal),
    notices: list(data.notices, text),
  }
}

export function decodeOrder(value: unknown) {
  const data = object(value)
  return {
    id: text(data.id),
    status: choice(data.status, [
      'pending_payment',
      'cancelled',
      'expired',
      'capture_pending',
      'payment_review',
      'paid',
      'refund_pending',
      'refund_review',
      'refunded',
    ] as const),
    created_at: timestamp(data.created_at),
    expires_at: timestamp(data.expires_at),
    snapshot: decodeCart(data.snapshot),
  }
}
export type Order = ReturnType<typeof decodeOrder>

export function decodePayment(value: unknown) {
  const data = object(value)
  choice(data.environment, ['sandbox'] as const)
  choice(data.merchant_mode, ['shared'] as const)
  return {
    order_id: text(data.order_id),
    state: choice(data.state, [
      'creating',
      'ready',
      'capture_pending',
      'completed',
      'failed',
      'needs_review',
    ] as const),
    provider_order_id: nullable(data.provider_order_id, text),
    capture_id: nullable(data.capture_id, text),
    verified_at: nullable(data.verified_at, timestamp),
    amount: decodePrice(data.amount),
  }
}
export type Payment = ReturnType<typeof decodePayment>

export function isVerifiedPaid(order: Order, payment: Payment | null) {
  return (
    order.status === 'paid' &&
    payment?.order_id === order.id &&
    payment.state === 'completed' &&
    Boolean(payment.capture_id) &&
    Boolean(payment.verified_at)
  )
}
