import { privateRequest } from './session'
import { integer, object, page, text } from './decode'
export type HistoryKind = 'analyses' | 'quality-evaluations' | 'price-observations' | 'price-comparisons' | 'sourcing-inputs' | 'supplier-quotes' | 'supplier-comparisons' | 'pricing-reviews' | 'passports'

export function getHistoryPage(product: string, kind: HistoryKind, offset: number, input: string | undefined, signal?: AbortSignal) {
  const nested = kind === 'supplier-quotes' || kind === 'supplier-comparisons'
  if (nested && !input) throw new Error('Choose a sourcing input first.')
  const path: `/${string}` = nested ? `/products/${product}/sourcing-inputs/${input}/${kind}` : `/products/${product}/${kind}`
  return privateRequest(`${path}?limit=20&offset=${offset}`, page(value => {
    const data = object(value)
    const id = text(data.id)
    const details = data.details ? object(data.details) : data
    const label = [details.label, details.supplier_name, data.candidate_label, data.reviewed_on, data.as_of_date, details.observed_on, data.created_at, data.status]
      .filter((value): value is string => typeof value === 'string').join(' · ')
    const revision = data.revision === undefined ? '' : ` · revision ${integer(data.revision)}`
    const source = details.source ? object(details.source) : null
    const quantityValue = details.quantity ?? details.package_quantity
    const quantity = quantityValue ? object(quantityValue) : null
    const context = [details.price ?? details.package_price, quantity ? `${quantity.value} ${quantity.unit}` : '', details.location, source?.name, source?.reference, details.quality_notes, details.availability]
      .filter(value => typeof value === 'string' && value).join(' · ')
    return { id, label: `${label || id}${revision}${context ? ` · ${context}` : ''} · ${id.slice(0, 8)}` }
  }), { signal })
}
