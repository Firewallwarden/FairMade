import { useCallback, useState } from 'react'
import { useResource } from '../hooks/useResource'
import { ErrorNotice } from './Feedback'
import { isVerifiedRefund } from '../services/order-care-contract'
import type { RefundRequestPage } from '../services/refund-list'
import { usd } from '../utils/presentation'

export function RefundRequestList({ title, loadPage, orderPath = 'orders' }: {
  title: string
  loadPage: (offset: number, signal?: AbortSignal) => Promise<RefundRequestPage>
  orderPath?: string
}) {
  const [offset, setOffset] = useState(0)
  const resource = useResource(useCallback(signal => loadPage(offset, signal), [offset, loadPage]))
  return <section className="workspace-panel">
    <h2>{title}</h2>
    <p>These are saved sandbox refund requests. Approval and pending states do not confirm a completed refund. Open an order for available actions and recovery controls.</p>
    <ErrorNotice error={resource.error} />
    {resource.loading && <p role="status">Loading refund requests…</p>}
    {resource.data && !resource.data.items.length && <p>No refund requests on this page.</p>}
    {resource.data?.items.map(item => <article key={item.id} className="workspace-panel">
      <h3><a href={`#/${orderPath}/${item.order_id}`}>Order {item.order_id}</a></h3>
      <p>Requested {new Date(item.created_at).toLocaleString()} · {usd(item.amount.amount)}</p>
      <p>Saved state: <strong>{item.state.replaceAll('_', ' ')}</strong>. {isVerifiedRefund(item) ? 'Backend-verified sandbox refund completed.' : 'No completed refund is confirmed here.'}</p>
      <p>Reason: {item.reason}</p>
      {item.decision && <p>Decision: {item.decision}. {item.decision_reason}</p>}
      {(item.state === 'refund_pending' || item.state === 'needs_review') && <p>Outcome uncertain. Use the order’s verification controls before retrying or assuming failure.</p>}
      <a href={`#/${orderPath}/${item.order_id}`}>Open order and refund controls</a>
    </article>)}
    <div className="workspace-actions">
      <button className="calculator-secondary" disabled={resource.loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous requests</button>
      <button className="calculator-secondary" disabled={resource.loading || !resource.data || resource.data.items.length < 20} onClick={() => setOffset(offset + 20)}>Next requests</button>
      <button className="calculator-secondary" disabled={resource.loading} onClick={resource.reload}>Refresh refund requests</button>
    </div>
  </section>
}
