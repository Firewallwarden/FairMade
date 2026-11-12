import { useCallback, useRef, useState } from 'react'
import { useAction } from '../../hooks/useAction'
import { useResource } from '../../hooks/useResource'
import { ErrorNotice } from '../../components/Feedback'
import { approveDescription, editDescription, generateDescription, getDescriptionDrafts } from '../../services/descriptions'

type Draft = Awaited<ReturnType<typeof generateDescription>>
export function DescriptionStep({ productId, onApplied }: { productId: string; onApplied: () => void }) {
  const [offset, setOffset] = useState(0)
  const resource = useResource(useCallback((signal) => getDescriptionDrafts(productId, offset, signal), [productId, offset]))
  const [draft, setDraft] = useState<Draft | null>(null)
  const [tone, setTone] = useState<'plain' | 'friendly'>('plain')
  const request = useRef<{ tone: string; id: string } | null>(null)
  const action = useAction()
  return <section className="workspace-panel"><h2>A little help finding the words.</h2>
    <p>Generate private copy with the local model, then review every factual and quality claim. Approval updates the private product only. Public descriptions need separate Passport approval.</p>
    <ErrorNotice error={resource.error || action.error} />
    {action.notice && <p className="calculator-notice" role="status">{action.notice}</p>}
    <label className="calculator-field">Tone<select value={tone} disabled={action.busy} onChange={(event) => setTone(event.target.value === 'friendly' ? 'friendly' : 'plain')}><option value="plain">Plain and clear</option><option value="friendly">Warm and friendly</option></select></label>
    <div className="workspace-actions"><button className="calculator-secondary" disabled={action.busy} onClick={() => action.run(async () => {
      if (request.current?.tone !== tone) request.current = { tone, id: crypto.randomUUID() }
      setDraft(await generateDescription(productId, tone, request.current.id))
      request.current = null
      resource.reload()
    }, 'Draft saved privately. Review and edit it before approval.')}>{action.busy ? 'Working with the local model…' : 'Generate private draft'}</button></div>
    {resource.loading && <p role="status">Loading copy history…</p>}
    {resource.data && <label className="calculator-field">Saved drafts<select value={draft?.id ?? ''} disabled={action.busy} onChange={(event) => setDraft(resource.data?.items.find((item) => item.id === event.target.value) ?? null)}>
      <option value="">Choose a private draft</option>{resource.data.items.map((item) => <option key={item.id} value={item.id}>{item.state} · revision {item.revision} · {item.id.slice(0, 8)}</option>)}
    </select></label>}
    <div className="workspace-actions"><button className="calculator-secondary" disabled={!offset || action.busy} onClick={() => { setDraft(null); setOffset(offset - 20) }}>Previous drafts</button><button className="calculator-secondary" disabled={action.busy || (resource.data?.items.length ?? 0) < 20} onClick={() => { setDraft(null); setOffset(offset + 20) }}>Next drafts</button></div>
    {draft && <DescriptionEditor key={`${draft.id}-${draft.revision}-${draft.state}`} draft={draft} productId={productId} onSaved={setDraft} onApplied={onApplied} />}
  </section>
}

function DescriptionEditor({ draft, productId, onSaved, onApplied }: { draft: Draft; productId: string; onSaved: (draft: Draft) => void; onApplied: () => void }) {
  const [copy, setCopy] = useState(draft.description)
  const [approved, setApproved] = useState(false)
  const action = useAction()
  const dirty = copy !== draft.description
  return <div><ErrorNotice error={action.error} /><ul>{draft.notices.map((notice, index) => <li key={index}>{notice}</li>)}</ul>
    <details><summary>Original AI draft</summary><p>{draft.generated_text}</p></details>
    <form onSubmit={(event) => {
      event.preventDefault()
      void action.run(async () => onSaved(await editDescription(productId, draft.id, draft.revision, copy.trim())))
    }}><label className="calculator-field">Review and edit the description<textarea value={copy} required maxLength={2000} rows={6} disabled={action.busy || draft.state === 'approved'} onChange={(event) => { setCopy(event.target.value); setApproved(false) }} /></label>
      <div className="workspace-actions"><button type="submit" className="calculator-secondary" disabled={!dirty || action.busy || draft.state === 'approved'}>Save edited draft</button></div>
    </form>
    {draft.state === 'approved' ? <p className="calculator-notice">Approved and applied privately. Publication is separate.</p> : <>
      <h3>Exact saved copy to apply</h3><p>{draft.description}</p>{dirty && <p>Save edits before approving.</p>}
      <label className="workspace-check"><input type="checkbox" checked={approved} disabled={dirty || action.busy} onChange={(event) => setApproved(event.target.checked)} />I reviewed this exact text and its factual claims.</label>
      <button className="button-primary" disabled={dirty || !approved || action.busy} onClick={() => action.run(async () => {
        onSaved(await approveDescription(productId, draft.id, draft.revision, draft.preview_hash)); onApplied()
      })}>Approve & apply privately</button>
    </>}
  </div>
}
