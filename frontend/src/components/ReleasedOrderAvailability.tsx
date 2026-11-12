import { useCallback } from 'react'
import { getCatalogListing } from '../services/commerce'
import type { Order } from '../services/order-contract'
import { useResource } from '../hooks/useResource'
import { ErrorNotice } from './Feedback'

export function ReleasedOrderAvailability({ order }: { order: Order }) {
  const resource = useResource(useCallback(async (signal) => {
    return Promise.all(order.snapshot.items.map(async item => {
      try {
        const listing = await getCatalogListing(item.listing_id, signal)
        return { id: item.listing_id, title: item.listing.product.title, availability: listing.availability }
      } catch {
        return { id: item.listing_id, title: item.listing.product.title, availability: null }
      }
    }))
  }, [order]))
  return <section className="workspace-panel">
    <h3>Availability after cancellation</h3>
    <p>The backend releases cancelled order reservations. Current availability is a snapshot and does not reserve stock.</p>
    <ErrorNotice error={resource.error} />
    {resource.loading && <p role="status">Refreshing availability…</p>}
    <ul>{resource.data?.map(item => <li key={item.id}>
      {item.title}: {item.availability ? `${item.availability.status} · ${item.availability.available_units ?? 'unknown'} selling units. ${item.availability.notice}` : 'Availability could not be loaded. The listing may be hidden; check private inventory for current stock.'}
    </li>)}</ul>
    <button className="calculator-secondary" disabled={resource.loading} onClick={resource.reload}>Refresh availability</button>
  </section>
}
