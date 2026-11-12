import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { ErrorNotice, SignInPrompt } from '../components/Feedback'
import { Field } from '../components/FormFields'
import { PassportView } from '../components/PassportView'
import {
  createOrder,
  getCatalogListing,
  previewOrder,
} from '../services/commerce'
import { useSession } from '../services/session'
import { useResource } from '../hooks/useResource'
import { useAction } from '../hooks/useAction'
import { usd } from '../utils/presentation'
import { publicMediaUrl } from '../services/media'
import type { CartRequest } from '../services/order-contract'
import { ApiError } from '../services/http'

export function ListingPage({ id }: { id: string }) {
  const resource = useResource(
    useCallback((signal) => getCatalogListing(id, signal), [id]),
  )
  const session = useSession()
  const action = useAction()
  const [quote, setQuote] = useState<{
    request: CartRequest
    key: string
    preview: Awaited<ReturnType<typeof previewOrder>>
  } | null>(null)
  const [reservationStarted, setReservationStarted] = useState(false)

  function preview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const card = resource.data
    if (!card) return
    const quantity = Number(
      new FormData(event.currentTarget).get('purchase-quantity'),
    )
    const request = {
      items: [
        {
          listing_id: id,
          expected_listing_revision: card.published_revision,
          quantity,
        },
      ],
    }
    void action.run(async () => {
      setQuote(null)
      setQuote({
        request,
        key: crypto.randomUUID(),
        preview: await previewOrder(request),
      })
    })
  }

  return (
    <WorkspaceLayout
      title={resource.data?.payload.product.title ?? 'A little more about it.'}
    >
      <a href="#/market">← Back to the market</a>
      <div className="workspace-actions"><a className="calculator-secondary" href={`#/assistant/buyer/${id}`}>Ask FairMade about this price</a></div>
      <ErrorNotice error={resource.error || action.error} />
      {resource.loading && <p role="status">Loading this listing…</p>}
      {resource.data && (
        <>
          <section className="workspace-panel">
            <p className="eyebrow">
              {resource.data.payload.seller_display_name}
            </p>
            <p>
              {resource.data.payload.location ??
                'No public location label provided.'}
            </p>
            <div className="listing-gallery">
              {resource.data.payload.photos.map((photo) => (
                <img
                  key={photo.id}
                  src={publicMediaUrl(photo.src)}
                  alt={photo.alt_text}
                  width={photo.width}
                  height={photo.height}
                />
              ))}
            </div>
            <p className="listing-price">
              {usd(resource.data.payload.price.amount)}{' '}
              <span>per {resource.data.payload.product.selling_unit}</span>
            </p>
            <p>{resource.data.payload.summary}</p>
            {resource.data.payload.selling_quantity && (
              <p>
                One selling unit contains{' '}
                {resource.data.payload.selling_quantity.value}{' '}
                {resource.data.payload.selling_quantity.unit}.
              </p>
            )}
            {resource.data.payload.unit_price && (
              <p>
                Standard unit price:{' '}
                {resource.data.payload.unit_price.amount === null
                  ? 'Below display precision'
                  : usd(resource.data.payload.unit_price.amount)}{' '}
                per {resource.data.payload.unit_price.reference_unit}. Based on
                seller-reported quantity.
              </p>
            )}
            <p>
              {resource.data.availability.status === 'available'
                ? `${resource.data.availability.available_units} selling units available.`
                : resource.data.availability.status === 'unavailable'
                  ? 'Currently unavailable.'
                  : 'Stock has not been configured.'}{' '}
              {resource.data.availability.notice}
            </p>
            <p>
              Local pickup demo. No shipping, taxes or delivery charges are
              calculated.
            </p>
          </section>
          <PassportView passport={resource.data.passport} />
          {!session ? (
            <SignInPrompt />
          ) : (
            <section className="workspace-panel">
              <h2>Bring a little goodness home.</h2>
              <p>
                Review the server-calculated merchandise subtotal before
                reserving stock. A reservation is not a payment.
              </p>
              <form onSubmit={preview} onChange={() => setQuote(null)}>
                <fieldset
                  disabled={
                    action.busy ||
                    reservationStarted ||
                    resource.data.availability.status !== 'available'
                  }
                  className="calculator-form"
                >
                  <legend className="sr-only">Choose purchase quantity</legend>
                  <Field
                    name="purchase-quantity"
                    title={`Quantity of ${resource.data.payload.product.selling_unit}`}
                    type="number"
                    min="1"
                    max={Math.min(
                      10000,
                      resource.data.availability.available_units ?? 0,
                    )}
                    step="1"
                    required
                    defaultValue="1"
                  />
                  <div className="workspace-actions">
                    <button className="button-primary" type="submit">
                      Review purchase subtotal
                    </button>
                  </div>
                </fieldset>
              </form>
              {quote && (
                <div className="calculator-notice">
                  <h3>Before you reserve</h3>
                  <p>
                    Merchandise subtotal:{' '}
                    <strong>{usd(quote.preview.subtotal.amount)}</strong>.
                  </p>
                  <ul>
                    {quote.preview.notices.map((notice, index) => (
                      <li key={index}>{notice}</li>
                    ))}
                  </ul>
                  <p>
                    Stock is held for 15 minutes after order creation. Sandbox
                    payment is confirmed separately.
                  </p>
                  <button
                    className="button-primary"
                    disabled={action.busy}
                    onClick={() =>
                      action.run(async () => {
                        setReservationStarted(true)
                        try {
                          const order = await createOrder(
                            quote.request,
                            quote.key,
                          )
                          window.location.hash = `/orders/${order.id}`
                        } catch (error) {
                          if (
                            error instanceof ApiError &&
                            error.status >= 400 &&
                            error.status < 500 &&
                            error.status !== 408
                          )
                            setReservationStarted(false)
                          throw error
                        }
                      })
                    }
                  >
                    {action.busy ? 'Reserving…' : 'Reserve stock & continue'}
                  </button>
                  <p className="workspace-muted">
                    If the request times out, retry this same reservation or
                    check Orders before starting another. The same retry key is
                    retained on this page.
                  </p>
                </div>
              )}
            </section>
          )}
        </>
      )}
      <div className="workspace-actions">
        <button
          className="calculator-secondary"
          disabled={reservationStarted}
          onClick={() => {
            setQuote(null)
            resource.reload()
          }}
        >
          Refresh current listing
        </button>
      </div>
    </WorkspaceLayout>
  )
}
