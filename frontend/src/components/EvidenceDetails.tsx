// Evidence is untrusted data rendered as text. Do not interpret source strings as HTML.
export function EvidenceDetails({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value === null || value === undefined) return <span>Unknown / not supplied</span>
  if (typeof value !== 'object') return <span>{String(value)}</span>
  if (depth >= 5) return <span>Additional nested detail is available in the saved source.</span>
  const entries = Object.entries(value)
  if (!entries.length) return <span>No details supplied</span>
  return <dl className="evidence-data">{entries.map(([key, item]) => <div key={key}>
    <dt>{Array.isArray(value) ? Number(key) + 1 : key.replaceAll('_', ' ')}</dt>
    <dd><EvidenceDetails value={item} depth={depth + 1} /></dd>
  </div>)}</dl>
}
