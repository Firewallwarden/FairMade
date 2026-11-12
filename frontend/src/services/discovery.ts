import { apiRequest } from './api'
import { browseMarket } from './commerce'
import { decodeCard } from './catalog-contract'
import { choice, list, money, object, page, text } from './decode'
import { decodeOrdering } from './market-contract'
import { nearbyListingRequest } from './discovery-contract'
import type { DiscoveryFilters } from './discovery-contract'

export async function searchListings(filters: DiscoveryFilters, offset: number, signal?: AbortSignal) {
  if (!filters.nearby) {
    const { q, product_type, location, availability, sort, reference_unit } = filters
    const result = await browseMarket({ q, product_type, location, availability, sort, reference_unit }, offset, signal)
    return { ...result, notices: [] as string[], items: result.items.map(card => ({ ...card, distance: null as string | null, area: null as string | null })) }
  }
  return apiRequest('/discovery/listings', value => {
    const data = object(value)
    choice(data.distance_basis, ['approximate_area_great_circle'] as const)
    return {
      ...page(value => {
        const row = object(value)
        const area = object(row.approximate_area)
        return { ...decodeCard(row.listing), distance: money(row.estimated_distance_km), area: text(area.label) }
      })(data),
      notices: list(data.notices, text),
      ordering: decodeOrdering(data.ordering),
    }
  }, { method: 'POST', json: nearbyListingRequest(filters, offset), signal })
}
