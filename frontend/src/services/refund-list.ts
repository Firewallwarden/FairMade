import { privateRequest } from './session'
import { object, page, text, timestamp } from './decode'
import { decodeRefund } from './order-care-contract'

export function decodeRefundListItem(value: unknown) {
  const data = object(value)
  return { ...decodeRefund(value), order_id: text(data.order_id), created_at: timestamp(data.created_at) }
}
export const getBuyerRefundRequests = (offset: number, signal?: AbortSignal) =>
  privateRequest(`/refund-requests?limit=20&offset=${offset}`, page(decodeRefundListItem), { signal })
export type RefundRequestPage = Awaited<ReturnType<typeof getBuyerRefundRequests>>
