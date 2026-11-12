import { useCallback, useState } from 'react'
import { useResource } from '../hooks/useResource'
import { getPickupHistory } from '../services/pickup-history'
import { ErrorNotice } from './Feedback'

export function PickupHistory({ orderId, seller }: { orderId: string; seller: boolean }) {
  const [offset, setOffset] = useState(0)
  const resource = useResource(useCallback(signal => getPickupHistory(orderId, seller, offset, signal), [orderId, seller, offset]))
  return <section className="workspace-panel">
    <h3>Recorded pickup timeline</h3>
    <p>These private updates and instructions are seller-reported, not independent proof of collection. Newest recorded changes appear first.</p>
    <ErrorNotice error={resource.error} />
    {resource.loading && <p role="status">Loading pickup history…</p>}
    {resource.data && !resource.data.items.length && <p>No pickup updates on this page.</p>}
    <ol>{resource.data?.items.map(item => <li key={item.revision}>
      <p><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time> · revision {item.revision} · <strong>{item.state.replaceAll('_', ' ')}</strong></p>
      <p className="private-instructions">{item.pickup_instructions ?? 'No instructions recorded.'}</p>
    </li>)}</ol>
    <div className="workspace-actions">
      <button className="calculator-secondary" disabled={resource.loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Newer pickup updates</button>
      <button className="calculator-secondary" disabled={resource.loading || !resource.data || resource.data.items.length < 20} onClick={() => setOffset(offset + 20)}>Older pickup updates</button>
      <button className="calculator-secondary" disabled={resource.loading} onClick={resource.reload}>Refresh pickup history</button>
    </div>
  </section>
}
