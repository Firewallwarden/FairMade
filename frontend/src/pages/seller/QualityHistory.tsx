import { useCallback, useState } from 'react'
import { useResource } from '../../hooks/useResource'
import { ErrorNotice } from '../../components/Feedback'
import { getHistoricalEvaluation, getQualityHistory } from '../../services/quality-history'
import { matchesCurrentRequirements } from '../../services/quality-history-contract'
import type { QualityRule } from '../../services/quality-contract'
import { ruleDescription } from '../../utils/presentation'

export function QualityHistory({ productId, current }: { productId: string; current: { revision: number; rules: QualityRule[] } }) {
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState('')
  const history = useResource(useCallback(signal => getQualityHistory(productId, offset, signal), [productId, offset]))
  return <section className="workspace-panel">
    <h3>Saved Quality Lock evaluations</h3>
    <ErrorNotice error={history.error} />
    {history.loading && <p role="status">Loading saved evaluations…</p>}
    {history.data && !history.data.items.length && <p>No saved evaluations on this page.</p>}
    <ul>{history.data?.items.map(item => <li key={item.id}>
      <button className="calculator-secondary" aria-pressed={selected === item.id} onClick={() => setSelected(item.id)}>{item.candidate_label} · {new Date(item.created_at).toLocaleString()} · {item.status}</button>
    </li>)}</ul>
    <div className="workspace-actions">
      <button className="calculator-secondary" disabled={history.loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous evaluations</button>
      <button className="calculator-secondary" disabled={history.loading || !history.data || history.data.items.length < 20} onClick={() => setOffset(offset + 20)}>Next evaluations</button>
      <button className="calculator-secondary" onClick={history.reload}>Refresh evaluations</button>
    </div>
    {selected && <EvaluationDetails key={selected} productId={productId} evaluationId={selected} current={current} />}
  </section>
}
function EvaluationDetails({ productId, evaluationId, current }: { productId: string; evaluationId: string; current: { revision: number; rules: QualityRule[] } }) {
  const resource = useResource(useCallback(signal => getHistoricalEvaluation(productId, evaluationId, signal), [productId, evaluationId]))
  const saved = resource.data
  return <article className="workspace-panel">
    <ErrorNotice error={resource.error} />
    {resource.loading && <p role="status">Loading recorded evaluation…</p>}
    {saved && <>
      <h4>{saved.candidate_label}: {saved.status.replaceAll('_', ' ')}</h4>
      <p>Recorded {new Date(saved.created_at).toLocaleString()} against requirements revision {saved.rule_revision}. Claims are seller-reported and unverified.</p>
      {!matchesCurrentRequirements(saved, current) && <p role="alert">Historical result: these recorded requirements differ from current revision {current.revision}. This result does not establish compliance with current requirements.</p>}
      <h4>Recorded requirements and claims</h4>
      {!saved.rules_snapshot.length && <p>No requirements were configured; compliance was not established.</p>}
      <ul>{saved.rules_snapshot.map(rule => {
        const claim = saved.claims[rule.key]
        return <li key={rule.key}><strong>{rule.label}</strong>: {ruleDescription(rule)}. Reported claim: {claim ? `${String(claim.value)}${claim.type === 'numeric' ? ` ${claim.unit}` : ''}` : 'Unknown / not supplied'}.</li>
      })}</ul>
      <h4>Individual checks</h4>
      <ul>{saved.checks.map(check => <li key={check.key}>{check.label}: {check.status} — {check.message}</li>)}</ul>
      <p>{saved.status === 'failed' ? 'A failed mandatory check cannot be treated as an acceptable saving.' : 'Matching reported claims are not independent verification. Missing evidence cannot establish compliance.'}</p>
    </>}
    <button className="calculator-secondary" disabled={resource.loading} onClick={resource.reload}>Reload recorded evaluation</button>
  </article>
}
