import { useCallback } from 'react'
import { useResource } from '../../hooks/useResource'
import { useAction } from '../../hooks/useAction'
import { ErrorNotice } from '../../components/Feedback'
import { getPublications } from '../../services/seller'
import { withdrawPassportPublication } from '../../services/passport-publications'

export function PassportPublications({ productId, draftId, onWithdrawn }: {
  productId: string; draftId: string; onWithdrawn: () => void
}) {
  const resource = useResource(useCallback(() => getPublications(productId, draftId), [productId, draftId]))
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
      {item.state === 'published' && <button className="calculator-secondary" disabled={action.busy} onClick={() => {
        if (!window.confirm('Withdraw this published Passport and hide its linked listings? Copies already received cannot be recalled.')) return
        void action.run(async () => {
          await withdrawPassportPublication(productId, draftId, item.id)
          onWithdrawn()
          resource.reload()
        }, 'Passport withdrawn. Linked listings are no longer publicly available.')
      }}>Withdraw published Passport</button>}
    </article>)}
    <button className="calculator-secondary" disabled={resource.loading || action.busy} onClick={resource.reload}>Refresh publication history</button>
  </section>
}
