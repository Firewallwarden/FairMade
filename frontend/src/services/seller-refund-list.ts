import { privateRequest } from './session'
import { page } from './decode'
import { decodeRefundListItem } from './refund-list'

export const getSellerRefundRequests = (offset: number, signal?: AbortSignal) =>
  privateRequest(`/seller/refund-requests?limit=20&offset=${offset}`, page(decodeRefundListItem), { signal })
