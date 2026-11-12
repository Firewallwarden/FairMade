import { privateRequest } from './session'
import { decodeOrder } from './order-contract'

export const cancelSellerOrder = (id: string) =>
  privateRequest(`/seller/orders/${id}/cancel`, decodeOrder, { method: 'POST' })
