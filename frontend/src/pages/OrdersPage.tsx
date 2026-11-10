import { useCallback, useState } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { ErrorNotice, SignInPrompt } from '../components/Feedback'
import { useSession } from '../services/session'
import { getOrders } from '../services/commerce'
import { useResource } from '../hooks/useResource'
import { usd } from '../utils/presentation'

export function OrdersPage() {
  const session = useSession()
  return (
    <WorkspaceLayout
      title="Good things in motion."
      intro="Check purchases, reservations and backend-confirmed payment status."
    >
      {!session ? (
        <SignInPrompt />
      ) : (
        <OrderList key={session.account.roles.includes('seller') ? 'seller' : 'buyer'} sellerAllowed={session.account.roles.includes('seller')} />
      )}
    </WorkspaceLayout>
  )
}

function OrderList({ sellerAllowed }: { sellerAllowed: boolean }) {
  const [seller, setSeller] = useState(false)
  const [offset, setOffset] = useState(0)
  const resource = useResource(
    useCallback(
      (signal) => getOrders(offset, seller, signal),
      [offset, seller],
    ),
  )
  return (
    <>
      {sellerAllowed && (
        <div className="workspace-actions">
          <button
            className="calculator-secondary"
            aria-pressed={!seller}
            onClick={() => {
              setSeller(false)
              setOffset(0)
            }}
          >
            My purchases
          </button>
          <button
            className="calculator-secondary"
            aria-pressed={seller}
            onClick={() => {
              setSeller(true)
              setOffset(0)
            }}
          >
            My seller orders
          </button>
        </div>
      )}
      <ErrorNotice error={resource.error} />
      {resource.loading && <p role="status">Loading orders…</p>}
      {resource.data && (
        <>
          {!resource.data.items.length && (
            <div className="workspace-empty">
              <h2>A little room for good things.</h2>
              <p>No orders on this page.</p>
              <a href="#/market">Browse the market</a>
            </div>
          )}
          <div className="workspace-grid">
            {resource.data.items.map((order) => (
              <article className="workspace-panel" key={order.id}>
                <span className="workspace-status">
                  {order.status.replaceAll('_', ' ')}
                </span>
                <h2>
                  {order.snapshot.items
                    .map((item) => item.listing.product.title)
                    .join(', ')}
                </h2>
                <p>
                  {usd(order.snapshot.subtotal.amount)} ·{' '}
                  {new Date(order.created_at).toLocaleString()}
                </p>
                <a
                  href={`#/${seller ? 'seller-orders' : 'orders'}/${order.id}`}
                >
                  View order {order.id.slice(0, 8)}
                </a>
              </article>
            ))}
          </div>
          <div className="workspace-actions">
            <button
              className="calculator-secondary"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - 20))}
            >
              Previous
            </button>
            <button
              className="calculator-secondary"
              disabled={resource.data.items.length < 20}
              onClick={() => setOffset(offset + 20)}
            >
              Next
            </button>
          </div>
        </>
      )}
      <button className="calculator-secondary" onClick={resource.reload}>
        Refresh orders
      </button>
    </>
  )
}
