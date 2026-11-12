import { apiRequest } from './api'
import { privateRequest } from './session'
import { ApiError } from './http'
import {
  empty,
  integer,
  list,
  money,
  nullable,
  object,
  page,
  text,
} from './decode'
import {
  decodeMessages,
  decodeMessage,
  decodePickup,
  decodeRefund,
  decodeOwnReview,
  decodePublicReview,
} from './order-care-contract'

const orderPath = (id: string, seller: boolean) =>
  `${seller ? '/seller' : ''}/orders/${id}` as const
export const getMessages = (id: string, cursor: number, signal?: AbortSignal) =>
  privateRequest(
    `/orders/${id}/messages?limit=20&after_sequence=${cursor}`,
    decodeMessages,
    { signal },
  )
export const sendMessage = (
  id: string,
  request: { request_id: string; text: string },
) =>
  privateRequest(`/orders/${id}/messages`, decodeMessage, {
    method: 'POST',
    json: request,
  })
export const getPickup = (id: string, seller: boolean, signal?: AbortSignal) =>
  privateRequest(`${orderPath(id, seller)}/fulfillment`, decodePickup, {
    signal,
  })
export const updatePickup = (
  id: string,
  revision: number,
  state: 'preparing' | 'ready_for_pickup' | 'collected',
  instructions: string | null,
) =>
  privateRequest(`/seller/orders/${id}/fulfillment`, decodePickup, {
    method: 'PUT',
    json: {
      expected_revision: revision,
      state,
      pickup_instructions: instructions,
    },
  })
export async function getRefund(
  id: string,
  seller: boolean,
  signal?: AbortSignal,
) {
  try {
    return await privateRequest(
      `${orderPath(id, seller)}/refund-request`,
      decodeRefund,
      { signal },
    )
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}
export const requestRefund = (id: string, reason: string) =>
  privateRequest(`/orders/${id}/refund-request`, decodeRefund, {
    method: 'POST',
    json: { reason },
  })
export const approveRefund = (id: string, revision: number) =>
  privateRequest(`/seller/orders/${id}/refund-request/approve`, decodeRefund, {
    method: 'POST',
    json: { expected_revision: revision },
  })
export const denyRefund = (id: string, revision: number, reason: string) =>
  privateRequest(`/seller/orders/${id}/refund-request/deny`, decodeRefund, {
    method: 'POST',
    json: { expected_revision: revision, reason },
  })
export const reconcileRefund = (id: string, seller: boolean) =>
  privateRequest(
    `${orderPath(id, seller)}/refund-request/reconcile`,
    decodeRefund,
    { method: 'POST', json: {} },
  )
type ReviewContent = { rating: number; text: string; publish: true }
export const createReview = (
  orderId: string,
  listingId: string,
  content: ReviewContent,
) =>
  privateRequest(
    `/orders/${orderId}/listings/${listingId}/review`,
    decodeOwnReview,
    { method: 'POST', json: content },
  )
export const getOwnReviews = (offset: number, signal?: AbortSignal) =>
  privateRequest(
    `/account/product-reviews?limit=20&offset=${offset}`,
    page(decodeOwnReview),
    { signal },
  )
export const updateReview = (
  id: string,
  revision: number,
  content: ReviewContent,
) =>
  privateRequest(`/account/product-reviews/${id}`, decodeOwnReview, {
    method: 'PUT',
    json: { ...content, expected_revision: revision },
  })
export const withdrawReview = (id: string, revision: number) =>
  privateRequest(`/account/product-reviews/${id}/withdraw`, empty, {
    method: 'POST',
    json: { expected_revision: revision },
  })
export const getPublicReviews = (
  id: string,
  offset: number,
  signal?: AbortSignal,
) =>
  apiRequest(
    `/marketplace/listings/${id}/reviews?limit=20&offset=${offset}`,
    page(decodePublicReview),
    { signal },
  )
export const getReviewSummary = (id: string, signal?: AbortSignal) =>
  apiRequest(
    `/marketplace/listings/${id}/reviews/summary`,
    (value) => {
      const data = object(value)
      return {
        review_count: integer(data.review_count),
        average_rating: nullable(data.average_rating, money),
        notices: list(data.notices, text),
      }
    },
    { signal },
  )
