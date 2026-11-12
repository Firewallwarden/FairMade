import { useState } from 'react'
import { previewOrder, createOrder } from '../services/commerce'
import type { CartRequest } from '../services/order-contract'
import { ApiError } from '../services/http'
import { useAction } from '../hooks/useAction'
import { ErrorNotice } from './Feedback'
import { usd } from '../utils/presentation'

export function PlanPurchaseReview({
  cart,
  locked,
  onLock,
}: {
  cart: CartRequest
  locked: boolean
  onLock: (value: boolean) => void
}) {
  const action = useAction()
  const [quote, setQuote] = useState<{
    preview: Awaited<ReturnType<typeof previewOrder>>
    key: string
  } | null>(null)
  return (
    <section className="workspace-panel">
      <p className="eyebrow">Separate purchase review</p>
      <h2>Ready to turn the plan into an order?</h2>
      <p>
        The plan did not reserve anything. Recheck the current server subtotal
        here, then explicitly reserve stock. PayPal payment is a separate step.
      </p>
      <ErrorNotice error={action.error} />
      <button
        className="calculator-secondary"
        disabled={locked || action.busy}
        onClick={() =>
          action.run(async () => {
            setQuote(null)
            setQuote({
              preview: await previewOrder(cart),
              key: crypto.randomUUID(),
            })
          })
        }
      >
        Check current purchase subtotal
      </button>
      {quote && (
        <>
          <ul>
            {quote.preview.items.map((item) => (
              <li key={item.listing_id}>
                {item.listing.product.title} · {item.quantity} selling unit(s) ·{' '}
                {usd(item.subtotal.amount)}
              </li>
            ))}
          </ul>
          <p>
            Merchandise subtotal:{' '}
            <strong>{usd(quote.preview.subtotal.amount)}</strong>.
          </p>
          <ul>
            {quote.preview.notices.map((notice, index) => (
              <li key={index}>{notice}</li>
            ))}
          </ul>
          <button
            className="button-primary"
            disabled={action.busy}
            onClick={() =>
              action.run(async () => {
                onLock(true)
                try {
                  const order = await createOrder(cart, quote.key)
                  window.location.hash = `/orders/${order.id}`
                } catch (error) {
                  if (
                    error instanceof ApiError &&
                    error.status >= 400 &&
                    error.status < 500 &&
                    error.status !== 408
                  )
                    onLock(false)
                  throw error
                }
              })
            }
          >
            {action.busy
              ? 'Reserving selected stock…'
              : 'Reserve these items & continue'}
          </button>
          <p className="workspace-muted">
            An uncertain result retains the same reservation key and locks plan
            edits. Retry this same reservation or inspect Orders. Reload loses
            this page’s retry key; check Orders before creating another
            reservation.
          </p>
        </>
      )}
    </section>
  )
}
