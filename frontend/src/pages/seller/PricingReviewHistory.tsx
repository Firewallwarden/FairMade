import { useCallback, useState } from 'react'
import { useResource } from '../../hooks/useResource'
import { getReviewHistory, getSavedReview } from '../../services/review-history'
import { ErrorNotice } from '../../components/Feedback'
import { EvidenceDetails } from '../../components/EvidenceDetails'
import { PricingResults } from '../../components/PricingResults'

export function PricingReviewHistory({ productId }: { productId: string }) {
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState('')
  const history = useResource(useCallback(signal => getReviewHistory(productId, offset, signal), [productId, offset]))
  return <section className="workspace-panel">
    <h3>Reopen a complete saved pricing review</h3>
    <p>Historical reviews retain the economics and evidence recorded at the time. Reopening does not update their prices, source ages or Quality Locks.</p>
    <ErrorNotice error={history.error} />
    {history.loading && <p role="status">Loading saved pricing reviews…</p>}
    {history.data && !history.data.items.length && <p>No reviews on this page.</p>}
    <ul>{history.data?.items.map(item => <li key={item.id}>
      <button className="calculator-secondary" aria-pressed={selected === item.id} onClick={() => setSelected(item.id)}>{item.reviewed_on} · {item.id}</button>
    </li>)}</ul>
    <div className="workspace-actions">
      <button className="calculator-secondary" disabled={history.loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous reviews</button>
      <button className="calculator-secondary" disabled={history.loading || !history.data || history.data.items.length < 20} onClick={() => setOffset(offset + 20)}>Next reviews</button>
      <button className="calculator-secondary" disabled={history.loading} onClick={history.reload}>Refresh reviews</button>
    </div>
    {selected && <ReviewDetails key={selected} productId={productId} reviewId={selected} />}
  </section>
}
function ReviewDetails({ productId, reviewId }: { productId: string; reviewId: string }) {
  const resource = useResource(useCallback(signal => getSavedReview(productId, reviewId, signal), [productId, reviewId]))
  const saved = resource.data
  return <article className="workspace-panel">
    <ErrorNotice error={resource.error} />
    {resource.loading && <p role="status">Loading complete recorded review…</p>}
    {saved && <>
      <h3>Historical review dated {saved.reviewed_on}</h3>
      <p>Created {new Date(saved.created_at).toLocaleString()}. Seller-reported, unverified evidence. No current compliance, earnings or objective fairness verdict is implied.</p>
      <PricingResults result={saved.economics} unit={saved.unit} />
      <h4>Recorded explanations</h4>
      <ul>{saved.explanations.map((item, index) => <li key={index}>{item.message}</li>)}</ul>
      <h4>Recorded warnings</h4>
      <ul>{saved.warnings.map((warning, index) => <li key={index}>{warning.replaceAll('_', ' ')}</li>)}</ul>
      <details><summary>Recorded Quality Lock context</summary><EvidenceDetails value={saved.quality} /></details>
      <details><summary>Recorded market context</summary><EvidenceDetails value={saved.market} /></details>
      <details><summary>Complete recorded source evidence</summary>
        <p>Private source snapshots include the original inputs and limitations; these are not public Passport disclosures.</p>
        <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(saved.evidence, null, 2)}</pre>
      </details>
      <details><summary>Recorded evidence selections</summary><EvidenceDetails value={saved.request} /></details>
    </>}
    <button className="calculator-secondary" disabled={resource.loading} onClick={resource.reload}>Reload saved review</button>
  </article>
}
