import {
  choice,
  integer,
  list,
  money,
  nullable,
  object,
  text,
  timestamp,
} from './decode.ts'

export const expenseCategories = [
  'materials',
  'packaging',
  'transport',
  'utilities',
  'equipment',
  'overhead',
  'other',
] as const
export type ExpenseDetails = {
  merchant: string | null
  purchased_on: string | null
  currency: 'USD' | null
  subtotal: string | null
  tax: string | null
  total: string | null
  items: { description: string; line_total: string | null }[]
  category: (typeof expenseCategories)[number]
}
export function decodeExpenseDetails(value: unknown): ExpenseDetails {
  const data = object(value)
  return {
    merchant: nullable(data.merchant, text),
    purchased_on: nullable(data.purchased_on, text),
    currency: nullable(data.currency, (value) =>
      choice(value, ['USD'] as const),
    ),
    subtotal: nullable(data.subtotal, money),
    tax: nullable(data.tax, money),
    total: nullable(data.total, money),
    category: choice(data.category, expenseCategories),
    items: list(data.items, (value) => {
      const item = object(value)
      return {
        description: text(item.description),
        line_total: nullable(item.line_total, money),
      }
    }),
  }
}
export function decodeReceipt(value: unknown) {
  const data = object(value)
  const hash = text(data.preview_hash)
  if (!/^[a-f0-9]{64}$/.test(hash))
    throw new Error('Invalid receipt preview hash')
  return {
    id: text(data.id),
    revision: integer(data.revision),
    state: choice(data.state, ['draft', 'approved'] as const),
    created_at: timestamp(data.created_at),
    ocr_text: text(data.ocr_text),
    provenance: object(data.provenance),
    extracted: object(data.extracted),
    details: decodeExpenseDetails(data.details),
    preview_hash: hash,
    approval_blockers: list(data.approval_blockers, text),
    notices: list(data.notices, text),
  }
}
export function decodeExpense(value: unknown) {
  const data = object(value)
  choice(data.basis, ['seller_reviewed_unverified'] as const)
  return {
    id: text(data.id),
    receipt_id: text(data.receipt_id),
    created_at: timestamp(data.created_at),
    details: decodeExpenseDetails(data.details),
  }
}
export function validateReceiptImage(file: { size: number; type: string }) {
  if (!['image/png', 'image/jpeg'].includes(file.type))
    throw new Error('Choose a PNG or JPEG receipt image.')
  if (file.size <= 0 || file.size > 5 * 1024 * 1024)
    throw new Error('Receipt images must be nonempty and no larger than 5 MiB.')
}
export const receiptBlockerLabels: Record<string, string> = {
  MISSING_MERCHANT: 'Merchant is missing.',
  MISSING_PURCHASED_ON: 'Purchase date is missing.',
  MISSING_CURRENCY: 'Confirm the currency.',
  MISSING_TOTAL: 'Total is missing.',
  TOTAL_MUST_BE_POSITIVE: 'Total must be greater than zero.',
  SUBTOTAL_EXCEEDS_TOTAL: 'Subtotal exceeds the total.',
  TOTAL_MISMATCH: 'Subtotal plus tax does not match the total.',
  ITEM_TOTAL_MISMATCH: 'Line item totals do not match the saved subtotal.',
}
