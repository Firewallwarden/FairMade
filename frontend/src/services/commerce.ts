import { apiRequest } from './api'
import { ApiError } from './http'
import { privateRequest } from './session'
import {
  decodeCard,
  decodeDetail,
  decodePayPalConfig,
} from './catalog-contract'
import { decodeCart, decodeOrder, decodePayment } from './order-contract'
import type { CartRequest } from './order-contract'
import { page } from './decode'
import { object } from './decode'
import { decodeOrdering } from './market-contract'

export function browseMarket(
  filters: {
    q: string
    product_type: string
    location: string
    availability: string
    sort?: string
    reference_unit?: string
  },
  offset: number,
  signal?: AbortSignal,
) {
  const query = new URLSearchParams({ limit: '12', offset: String(offset) })
  Object.entries(filters).forEach(([key, value]) => {
    if (value.trim()) query.set(key, value.trim())
  })
  return apiRequest(
    `/marketplace/listings?${query}`,
    (value) => ({
      ...page(decodeCard)(value),
      ordering: decodeOrdering(object(value).ordering),
    }),
    {
      signal,
    },
  )
}
export const getCatalogListing = (id: string, signal?: AbortSignal) =>
  apiRequest(`/marketplace/listings/${id}`, decodeDetail, { signal })
export const previewOrder = (cart: CartRequest) =>
  privateRequest('/orders/preview', decodeCart, { method: 'POST', json: cart })
export const createOrder = (cart: CartRequest, key: string) =>
  privateRequest('/orders', decodeOrder, {
    method: 'POST',
    json: cart,
    headers: { 'Idempotency-Key': key },
  })
export const getOrders = (
  offset: number,
  seller: boolean,
  signal?: AbortSignal,
) =>
  privateRequest(
    `${seller ? '/seller' : ''}/orders?limit=20&offset=${offset}`,
    page(decodeOrder),
    { signal },
  )
export const getOrder = (id: string, seller: boolean, signal?: AbortSignal) =>
  privateRequest(`${seller ? '/seller' : ''}/orders/${id}`, decodeOrder, {
    signal,
  })
export const cancelOrder = (id: string) =>
  privateRequest(`/orders/${id}/cancel`, decodeOrder, { method: 'POST' })
export const getPayPalConfig = (signal?: AbortSignal) =>
  apiRequest('/paypal/config', decodePayPalConfig, { signal })
export async function getPayment(
  id: string,
  seller: boolean,
  signal?: AbortSignal,
) {
  try {
    return await privateRequest(
      `${seller ? '/seller' : ''}/orders/${id}/paypal-checkout`,
      decodePayment,
      { signal },
    )
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}
export const createCheckout = (id: string) =>
  privateRequest(`/orders/${id}/paypal-checkout`, decodePayment, {
    method: 'POST',
    json: {},
  })
export const captureCheckout = (id: string) =>
  privateRequest(`/orders/${id}/paypal-checkout/capture`, decodePayment, {
    method: 'POST',
    json: {},
  })
export const reconcileCheckout = (id: string, seller: boolean) =>
  privateRequest(
    `${seller ? '/seller' : ''}/orders/${id}/paypal-checkout/reconcile`,
    decodePayment,
    { method: 'POST', json: {} },
  )
