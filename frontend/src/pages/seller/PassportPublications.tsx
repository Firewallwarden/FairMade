import { useCallback, useState } from 'react'
import { useResource } from '../../hooks/useResource'
import { useAction } from '../../hooks/useAction'
import { ErrorNotice } from '../../components/Feedback'
import { getPublications } from '../../services/seller'
import { withdrawPassportPublication } from '../../services/passport-publications'
import { PassportView } from '../../components/PassportView'

export function PassportPublications({ productId, draftId, onWithdrawn }: {
  productId: string; draftId: string; onWithdrawn: () => void
}) {
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<Awaited<ReturnType<typeof getPublications>>['items'][number] | null>(null)
  const resource = useResource(useCallback(signal => getPublications(productId, draftId, offset, signal), [productId, draftId, offset]))
  const action = useAction()
  return <section className="workspace-panel">
    <h3>Passport publication history</h3>
    <p>Withdrawing a Passport removes public API access and hides linked listings. Existing orders and copies already received are retained. This is separate from hiding a listing or withdrawing a storefront.</p>
    <ErrorNotice error={resource.error || action.error} />
    {resource.loading && <p role="status">Loading publications…</p>}
    {action.notice && <p role="status">{action.notice}</p>}
    {resource.data && !resource.data.items.length && <p>No publications for this draft.</p>}
    {resource.data?.items.map(item => <article key={item.id} className="workspace-panel">
      <p>Revision {item.revision} · {item.state} · {item.id}</p>
      <button className="calculator-secondary" onClick={() => setSelected(item)}>Inspect recorded publication {item.revision}</button>
      {item.state === 'published' && <button className="calculator-secondary" disabled={action.busy} onClick={() => {
        if (!window.confirm('Withdraw this published Passport and hide its linked listings? Copies already received cannot be recalled.')) return
        void action.run(async () => {
          await withdrawPassportPublication(productId, draftId, item.id)
          onWithdrawn()
          resource.reload()
        }, 'Passport withdrawn. Linked listings are no longer publicly available.')
      }}>Withdraw published Passport</button>}
    </article>)}
    <div className="workspace-actions">
      <button className="calculator-secondary" disabled={resource.loading || action.busy || offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Newer publications</button>
      <button className="calculator-secondary" disabled={resource.loading || action.busy || !resource.data || resource.data.items.length < 20} onClick={() => setOffset(offset + 20)}>Older publications</button>
    </div>
    {selected && <section><h4>Recorded publication revision {selected.revision}</h4><p>Historical snapshot. Its payload does not establish current publication status.</p><PassportView passport={selected.payload} /></section>}
    <button className="calculator-secondary" disabled={resource.loading || action.busy} onClick={resource.reload}>Refresh publication history</button>
  </section>
}
