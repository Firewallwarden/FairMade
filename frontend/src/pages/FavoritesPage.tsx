import { useCallback, useState } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { ErrorNotice, SignInPrompt } from '../components/Feedback'
import { useSession } from '../services/session'
import { useAction } from '../hooks/useAction'
import { useResource } from '../hooks/useResource'
import { getFavorites, removeFavorite, saveFavorite } from '../services/favorites'
import { usd } from '../utils/presentation'

export function SaveFavorite({ listingId }: { listingId: string }) {
  const session = useSession()
  const action = useAction()
  return session ? <div><ErrorNotice error={action.error} />{action.notice ? <p role="status">{action.notice} <a href="#/favorites">View saved goods</a></p> :
    <button className="calculator-secondary" disabled={action.busy} onClick={() => action.run(async () => { await saveFavorite(listingId) }, 'Saved to your private favorites.')}>Save this product</button>}</div> : null
}

export function FavoritesPage() {
  const session = useSession()
  return <WorkspaceLayout title="Your kind of good." intro="Private bookmarks of products you want to revisit."><>{!session ? <SignInPrompt /> : <FavoriteList />}</></WorkspaceLayout>
}
function FavoriteList() {
  const [offset, setOffset] = useState(0)
  const resource = useResource(useCallback((signal) => getFavorites(offset, signal), [offset]))
  const action = useAction()
  return <><ErrorNotice error={resource.error || action.error} />{resource.loading && <p role="status">Loading your saved products…</p>}
    {resource.data && <>
      {!resource.data.items.length && <div className="workspace-empty">No saved products on this page. <a href="#/market">Explore the market.</a></div>}
      <div className="workspace-grid">{resource.data.items.map((item) => <article className="workspace-panel" key={item.id}>
        {item.listing_visible && item.listing ? <><h2>{item.listing.payload.product.title}</h2><p>{usd(item.listing.payload.price.amount)} / {item.listing.payload.product.selling_unit}</p><a href={`#/market/${item.listing_id}`}>View current listing</a></> : <><h2>Currently unavailable listing</h2><p>Your bookmark remains, but withdrawn public details are hidden.</p></>}
        <div className="workspace-actions"><button className="calculator-secondary" disabled={action.busy} onClick={() => action.run(async () => { await removeFavorite(item.id); resource.reload() })}>Remove bookmark</button></div>
      </article>)}</div>
      <div className="workspace-actions"><button className="calculator-secondary" disabled={!offset} onClick={() => setOffset(offset - 20)}>Previous</button><button className="calculator-secondary" disabled={resource.data.items.length < 20} onClick={() => setOffset(offset + 20)}>Next</button></div>
    </>}
    <button className="calculator-secondary" onClick={resource.reload}>Refresh favorites</button>
  </>
}
