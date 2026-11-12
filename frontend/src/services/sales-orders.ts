import { privateRequest } from './session'
import { page } from './decode'
import { decodeSalesOrder } from './sales-contract'

export const getSalesOrders = (start: string, end: string, offset: number, signal?: AbortSignal) =>
  privateRequest(`/seller/sales/orders?${new URLSearchParams({ start_date: start, end_date: end, limit: '20', offset: String(offset) })}`, page(decodeSalesOrder), { signal })
