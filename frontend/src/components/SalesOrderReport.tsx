import { useCallback, useState } from 'react'
import { getSalesOrders } from '../services/sales-orders'
import { useResource } from '../hooks/useResource'
import { Field } from './FormFields'
import { ErrorNotice } from './Feedback'
import { EvidenceDetails } from './EvidenceDetails'
import { fieldValue } from '../utils/form'
import { usd } from '../utils/presentation'

const amount = (value: string | null) => value === null ? 'Unknown / unavailable' : usd(value)
export function SalesOrderReport() {
  const [period, setPeriod] = useState(() => ({ start: new Date(Date.now() - 29 * 86400000).toISOString().slice(0, 10), end: new Date(Date.now() + 86400000).toISOString().slice(0, 10) }))
  const [offset, setOffset] = useState(0)
  const resource = useResource(useCallback(signal => getSalesOrders(period.start, period.end, offset, signal), [period, offset]))
  return <section className="workspace-panel">
    <h2>Itemized sandbox sales and estimated profitability</h2>
    <p>Only backend-verified sandbox captures in the UTC period are included. Refunds reflect completed refunds known now, even if completed later. This is a capture cohort, not cash movement or actual business earnings. Unknown fees and costs remain unknown.</p>
    <form className="calculator-form" onSubmit={event => {
      event.preventDefault()
      const fields = new FormData(event.currentTarget)
      setPeriod({ start: fieldValue(fields, 'sales-start'), end: fieldValue(fields, 'sales-end') })
      setOffset(0)
    }}>
      <div className="calculator-grid">
        <Field name="sales-start" title="Capture period start (UTC, inclusive)" type="date" required defaultValue={period.start} />
        <Field name="sales-end" title="Capture period end (UTC, exclusive)" type="date" required defaultValue={period.end} />
      </div>
      <p>Choose a period of 1–366 days.</p>
      <button className="button-primary" type="submit">Load itemized sales</button>
    </form>
    <ErrorNotice error={resource.error} />
    {resource.loading && <p role="status">Loading sales and cost coverage…</p>}
    {resource.data && !resource.data.items.length && <p>No verified sales on this page for the selected period.</p>}
    {resource.data?.items.map(sale => <article key={sale.order_id} className="workspace-panel">
      <h3><a href={`#/seller-orders/${sale.order_id}`}>Order {sale.order_id}</a></h3>
      <p>Capture verified {new Date(sale.captured_at).toLocaleString()}.</p>
      <dl className="calculator-metrics">
        <div><dt>Gross sales</dt><dd>{amount(sale.gross_sales)}</dd></div>
        <div><dt>Completed refunds</dt><dd>{amount(sale.completed_refunds)}</dd></div>
        <div><dt>Original processing fee</dt><dd>{amount(sale.processing_fee)} · {sale.fee_basis.replaceAll('_', ' ')}</dd></div>
        <div><dt>After refunds and fee</dt><dd>{amount(sale.after_refunds_and_fee)}</dd></div>
        <div><dt>Frozen estimated production cost</dt><dd>{amount(sale.estimated_production_cost)}</dd></div>
        <div><dt>Estimated profit</dt><dd>{amount(sale.estimated_profit)}</dd></div>
        <div><dt>Estimated margin (fraction)</dt><dd>{sale.estimated_margin ?? 'Unknown / unavailable'}</dd></div>
      </dl>
      <ul>{[...sale.profit_unavailable_reasons, ...sale.warnings].map((reason, index) => <li key={index}>{reason.replaceAll('_', ' ')}</li>)}</ul>
      <details><summary>Frozen private cost basis</summary><EvidenceDetails value={sale.cost_snapshot} /></details>
    </article>)}
    <div className="workspace-actions">
      <button className="calculator-secondary" disabled={resource.loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous sales</button>
      <button className="calculator-secondary" disabled={resource.loading || !resource.data || resource.data.items.length < 20} onClick={() => setOffset(offset + 20)}>Next sales</button>
      <button className="calculator-secondary" disabled={resource.loading} onClick={resource.reload}>Refresh sales report</button>
    </div>
  </section>
}
