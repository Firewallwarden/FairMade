import { privateRequest } from './session'
import { empty, page } from './decode'
import {
  decodeExpense,
  decodeReceipt,
  validateReceiptImage,
} from './receipt-contract'
import type { ExpenseDetails } from './receipt-contract'

export async function encodeReceiptImage(file: File) {
  validateReceiptImage(file)
  const bytes = new Uint8Array(await file.arrayBuffer())
  const png = [137, 80, 78, 71, 13, 10, 26, 10].every(
    (value, index) => bytes[index] === value,
  )
  const jpeg = bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255
  if (
    (file.type === 'image/png' && !png) ||
    (file.type === 'image/jpeg' && !jpeg)
  )
    throw new Error('The file contents do not match the selected image type.')
  let binary = ''
  for (let start = 0; start < bytes.length; start += 32768)
    binary += String.fromCharCode(...bytes.subarray(start, start + 32768))
  return btoa(binary)
}
export const getReceipts = (offset: number, signal?: AbortSignal) =>
  privateRequest(
    `/seller/receipt-drafts?limit=20&offset=${offset}`,
    page(decodeReceipt),
    { signal },
  )
export const getReceipt = (id: string, signal?: AbortSignal) =>
  privateRequest(`/seller/receipt-drafts/${id}`, decodeReceipt, { signal })
export const importReceipt = (request: {
  request_id: string
  image_base64: string
}) =>
  privateRequest('/seller/receipt-drafts', decodeReceipt, {
    method: 'POST',
    json: request,
    timeoutMs: 180000,
  })
export const editReceipt = (
  id: string,
  revision: number,
  details: ExpenseDetails,
) =>
  privateRequest(`/seller/receipt-drafts/${id}`, decodeReceipt, {
    method: 'PUT',
    json: { expected_revision: revision, details },
  })
export const approveReceipt = (id: string, revision: number, hash: string) =>
  privateRequest(`/seller/receipt-drafts/${id}/approve`, decodeExpense, {
    method: 'POST',
    json: { expected_revision: revision, preview_hash: hash, approved: true },
  })
export const discardReceipt = (id: string) =>
  privateRequest(`/seller/receipt-drafts/${id}`, empty, { method: 'DELETE' })
export const getExpenses = (offset: number, signal?: AbortSignal) =>
  privateRequest(
    `/seller/expenses?limit=20&offset=${offset}`,
    page(decodeExpense),
    { signal },
  )
