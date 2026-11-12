import { useCallback, useEffect, useState } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { ErrorNotice, SignInPrompt } from '../components/Feedback'
import { PayPalCheckout } from '../components/PayPalCheckout'
import {
  cancelOrder,
  getOrder,
  getPayment,
  reconcileCheckout,
} from '../services/commerce'
import { isVerifiedPaid } from '../services/order-contract'
import { useSession } from '../services/session'
import { useResource } from '../hooks/useResource'
import { useAction } from '../hooks/useAction'
import { usd } from '../utils/presentation'
import { OrderMessages } from '../components/OrderMessages'
import { PickupPanel, RefundPanel } from '../components/OrderCare'
import { WriteProductReview } from '../components/ProductReviews'

export function OrderPage({ id, seller }: { id: string; seller: boolean }) {
  const session = useSession()
  return (
    <WorkspaceLayout
      title={
        seller ? 'An order for your goods.' : 'A little goodness, on its way.'
      }
    >
      {!session ? (
        <SignInPrompt />
      ) : seller && !session.account.roles.includes('seller') ? (
        <p>Seller access is required.</p>
      ) : (
        <OrderDetails id={id} seller={seller} />
      )}
    </WorkspaceLayout>
  )
}

function OrderDetails({ id, seller }: { id: string; seller: boolean }) {
  const resource = useResource(
    useCallback(
      async (signal) => {
        const [order, payment] = await Promise.all([
          getOrder(id, seller, signal),
          getPayment(id, seller, signal),
        ])
        return { order, payment }
      },
      [id, seller],
    ),
  )
  const action = useAction()
  const [now, setNow] = useState(Date.now)
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])
  const order = resource.data?.order
  const payment = resource.data?.payment ?? null
  const unexpired = order ? Date.parse(order.expires_at) > now : false
  const canPay =
    order?.status === 'pending_payment' &&
    unexpired &&
    (!payment || payment.state === 'ready' || payment.state === 'creating')
  const verified = order ? isVerifiedPaid(order, payment) : false

  return (
    <>
      <a href="#/orders">← All orders</a>
      <ErrorNotice error={resource.error || action.error} />
      {action.notice && (
        <p className="calculator-notice" role="status">
          {action.notice}
        </p>
      )}
      {resource.loading && (
        <p role="status">Checking saved order and payment status…</p>
      )}
      {order && (
        <>
          <section className="workspace-panel">
            <p className="eyebrow">Order {order.id}</p>
            <h2>
              {verified
                ? 'Your sandbox payment is confirmed.'
                : order.status === 'cancelled'
                  ? 'This order was cancelled.'
                  : order.status === 'expired'
                    ? 'This reservation expired.'
                    : 'Here’s where things stand.'}
            </h2>
            <p>
              Backend order status:{' '}
              <strong>{order.status.replaceAll('_', ' ')}</strong>.
            </p>
            {payment && (
              <p>
                Backend payment status:{' '}
                <strong>{payment.state.replaceAll('_', ' ')}</strong>.
              </p>
            )}
            {verified && (
              <p role="status">
                The backend verified a completed PayPal sandbox capture at{' '}
                {new Date(payment?.verified_at ?? '').toLocaleString()}. This is
                a sandbox receipt, not a live purchase.
              </p>
            )}
            {order.status === 'pending_payment' && (
              <p>
                {unexpired
                  ? `Reservation expires in ${Math.max(0, Math.ceil((Date.parse(order.expires_at) - now) / 60000))} minute(s).`
                  : 'The reservation deadline has passed. Refresh saved status before continuing.'}
              </p>
            )}
            {(order.status === 'capture_pending' ||
              order.status === 'payment_review' ||
              payment?.state === 'needs_review') && (
              <p className="calculator-notice">
                The payment outcome needs backend verification. Do not start
                another order or assume a decline. Stock may remain held until
                reconciliation resolves it.
              </p>
            )}
            <ul>
              {order.snapshot.items.map((item) => (
                <li key={item.listing_id}>
                  {item.quantity} × {item.listing.product.title} (
                  {item.listing.product.selling_unit}) ·{' '}
                  {usd(item.unit_price.amount)} each ·{' '}
                  {usd(item.subtotal.amount)} subtotal
                </li>
              ))}
            </ul>
            <p>
              Merchandise subtotal:{' '}
              <strong>{usd(order.snapshot.subtotal.amount)}</strong>.
            </p>
            <details>
              <summary>Original order snapshot and limitations</summary>
              <ul>
                {order.snapshot.notices.map((notice, index) => (
                  <li key={index}>{notice}</li>
                ))}
              </ul>
              <p>
                The snapshot records the original quote. Current order and
                verified payment states above determine the outcome.
              </p>
            </details>
            <div className="workspace-actions">
              <button
                className="calculator-secondary"
                disabled={action.busy}
                onClick={resource.reload}
              >
                Refresh saved status
              </button>
              {payment && (
                <button
                  className="calculator-secondary"
                  disabled={action.busy}
                  onClick={() =>
                    action.run(async () => {
                      await reconcileCheckout(id, seller)
                      resource.reload()
                    }, 'Backend reconciliation requested; the refreshed saved status shows the outcome.')
                  }
                >
                  Verify with PayPal
                </button>
              )}
              {!seller &&
                order.status === 'pending_payment' &&
                (!payment ||
                  payment.state === 'ready' ||
                  payment.state === 'creating') && (
                  <button
                    className="calculator-secondary"
                    disabled={action.busy}
                    onClick={() =>
                      action.run(async () => {
                        await cancelOrder(id)
                        resource.reload()
                      }, 'The backend confirmed cancellation.')
                    }
                  >
                    Cancel unpaid order
                  </button>
                )}
            </div>
          </section>
          {!seller && canPay && (
            <PayPalCheckout orderId={id} onUpdated={resource.reload} />
          )}
          <PickupPanel orderId={id} seller={seller} />
          <RefundPanel order={order} seller={seller} onUpdated={resource.reload} />
          <OrderMessages orderId={id} />
          {!seller && verified && order.snapshot.items.map((item) => <WriteProductReview key={item.listing_id} orderId={id} listingId={item.listing_id} title={item.listing.product.title} />)}
          {!seller && !canPay && !verified && (
            <p>
              No new payment can be started in this state. Refresh the status or
              verify the existing checkout when available.
            </p>
          )}
        </>
      )}
    </>
  )
}
