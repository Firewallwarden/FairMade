import { useCallback } from 'react'
import {
  getPickup,
  getRefund,
  requestRefund,
  approveRefund,
  denyRefund,
  reconcileRefund,
  updatePickup,
} from '../services/order-care'
import { isVerifiedRefund } from '../services/order-care-contract'
import { useResource } from '../hooks/useResource'
import { useAction } from '../hooks/useAction'
import { ErrorNotice } from './Feedback'
import { TextArea } from './FormFields'
import { fieldValue } from '../utils/form'
import { usd } from '../utils/presentation'
import type { Order } from '../services/order-contract'

export function PickupPanel({
  orderId,
  seller,
}: {
  orderId: string
  seller: boolean
}) {
  const resource = useResource(
    useCallback(
      (signal) => getPickup(orderId, seller, signal),
      [orderId, seller],
    ),
  )
  const action = useAction()
  return (
    <section className="workspace-panel">
      <h2>Local pickup</h2>
      <ErrorNotice error={resource.error || action.error} />
      {resource.loading && (
        <p role="status">Checking private pickup progress…</p>
      )}
      {resource.data && (
        <>
          <p>
            Seller-reported status:{' '}
            <strong>{resource.data.state.replaceAll('_', ' ')}</strong>. This is
            not independent proof of handoff.
          </p>
          {resource.data.pickup_instructions && (
            <p className="private-instructions">
              {resource.data.pickup_instructions}
            </p>
          )}
          <ul>
            {resource.data.notices.map((notice, index) => (
              <li key={index}>{notice}</li>
            ))}
          </ul>
          {seller && (
            <form
              key={resource.data.revision}
              onSubmit={(event) => {
                event.preventDefault()
                const fields = new FormData(event.currentTarget)
                const state = fieldValue(fields, 'pickup-state')
                const revision = resource.data?.revision
                if (
                  revision === undefined ||
                  !['preparing', 'ready_for_pickup', 'collected'].includes(
                    state,
                  )
                )
                  return
                void action.run(async () => {
                  await updatePickup(
                    orderId,
                    revision,
                    state === 'collected'
                      ? 'collected'
                      : state === 'ready_for_pickup'
                        ? 'ready_for_pickup'
                        : 'preparing',
                    fieldValue(fields, 'pickup-instructions') || null,
                  )
                  resource.reload()
                })
              }}
            >
              <fieldset
                disabled={action.busy || !resource.data.updates_allowed}
                className="calculator-form"
              >
                <legend className="sr-only">
                  Update private pickup progress
                </legend>
                <label className="calculator-field">
                  Pickup progress
                  <select
                    name="pickup-state"
                    defaultValue={
                      resource.data.state === 'not_started'
                        ? 'preparing'
                        : resource.data.state
                    }
                  >
                    <option value="preparing">Preparing</option>
                    <option value="ready_for_pickup">Ready for pickup</option>
                    <option value="collected">Collected</option>
                  </select>
                </label>
                <TextArea
                  name="pickup-instructions"
                  title="Private pickup instructions (required for ready/collected)"
                  maxLength={2000}
                  defaultValue={resource.data.pickup_instructions ?? ''}
                />
                <div className="workspace-actions">
                  <button type="submit" className="calculator-secondary">
                    Save seller-reported pickup state
                  </button>
                </div>
              </fieldset>
            </form>
          )}
          {seller && !resource.data.updates_allowed && (
            <p>
              Updates are unavailable until verified payment and the backend’s
              refund/state checks permit them.
            </p>
          )}
        </>
      )}
      <button
        className="calculator-secondary"
        disabled={action.busy}
        onClick={resource.reload}
      >
        Refresh pickup
      </button>
    </section>
  )
}

export function RefundPanel({
  order,
  seller,
  onUpdated,
}: {
  order: Order
  seller: boolean
  onUpdated: () => void
}) {
  const resource = useResource(
    useCallback(
      (signal) => getRefund(order.id, seller, signal),
      [order.id, seller],
    ),
  )
  const action = useAction()
  const request = resource.data
  return (
    <section className="workspace-panel">
      <h2>Refunds, with a clear next step.</h2>
      <p>
        Full-order sandbox refunds require a buyer request and seller approval.
        A request or approval is not a verified refund. Refunds do not
        automatically restock products.
      </p>
      <ErrorNotice error={resource.error || action.error} />
      {resource.loading && <p role="status">Checking saved refund state…</p>}
      {request ? (
        <>
          <p>
            Request state: <strong>{request.state.replaceAll('_', ' ')}</strong>{' '}
            · {usd(request.amount.amount)}.
          </p>
          <p>Buyer’s reason: {request.reason}</p>
          {request.decision_reason && (
            <p>Seller’s reason: {request.decision_reason}</p>
          )}
          {isVerifiedRefund(request) && (
            <p className="calculator-notice" role="status">
              The backend verified this sandbox refund at{' '}
              {new Date(request.verified_at ?? '').toLocaleString()}.
            </p>
          )}
          {request.state === 'requested' && (
            <p>
              Awaiting seller review; the request alone does not refund the paid
              order.
            </p>
          )}
          {seller && request.state === 'requested' && (
            <>
              <form
                onSubmit={(event) => {
                  event.preventDefault()
                  if (!new FormData(event.currentTarget).has('approve-refund'))
                    return
                  void action.run(async () => {
                    try {
                      await approveRefund(order.id, request.revision)
                    } finally {
                      resource.reload()
                    }
                    onUpdated()
                  })
                }}
              >
                <label className="workspace-check">
                  <input
                    name="approve-refund"
                    type="checkbox"
                    required
                    disabled={action.busy}
                  />
                  I approve the full {usd(request.amount.amount)} sandbox refund
                  and want the backend to execute it.
                </label>
                <div className="workspace-actions">
                  <button
                    className="button-primary"
                    type="submit"
                    disabled={action.busy}
                  >
                    Approve & request sandbox refund
                  </button>
                </div>
              </form>
              <details>
                <summary>Deny the request with a shared reason</summary>
                <form
                  onSubmit={(event) => {
                    event.preventDefault()
                    const reason = fieldValue(
                      new FormData(event.currentTarget),
                      'refund-denial',
                    )
                    void action.run(async () => {
                      await denyRefund(order.id, request.revision, reason)
                      resource.reload()
                      onUpdated()
                    })
                  }}
                >
                  <TextArea
                    name="refund-denial"
                    title="Reason visible to the buyer"
                    required
                    maxLength={1000}
                  />
                  <button
                    type="submit"
                    className="calculator-secondary"
                    disabled={action.busy}
                  >
                    Deny refund request
                  </button>
                </form>
              </details>
            </>
          )}
          {request.decision === 'approved' && request.state !== 'refunded' && (
            <button
              className="calculator-secondary"
              disabled={action.busy}
              onClick={() =>
                action.run(async () => {
                  await reconcileRefund(order.id, seller)
                  resource.reload()
                  onUpdated()
                })
              }
            >
              Verify refund with PayPal
            </button>
          )}
        </>
      ) : (
        resource.data === null && (
          <>
            {!seller && order.status === 'paid' ? (
              <form
                onSubmit={(event) => {
                  event.preventDefault()
                  const reason = fieldValue(
                    new FormData(event.currentTarget),
                    'refund-reason',
                  )
                  void action.run(async () => {
                    await requestRefund(order.id, reason)
                    resource.reload()
                  }, 'Refund request saved for seller review.')
                }}
              >
                <TextArea
                  name="refund-reason"
                  title="Why are you requesting a full-order refund?"
                  required
                  maxLength={1000}
                />
                <div className="workspace-actions">
                  <button
                    className="calculator-secondary"
                    type="submit"
                    disabled={action.busy}
                  >
                    Request seller-reviewed refund
                  </button>
                </div>
              </form>
            ) : (
              <p>
                No refund request. Buyer requests become available only for
                eligible backend-paid orders.
              </p>
            )}
          </>
        )
      )}
      {action.notice && <p role="status">{action.notice}</p>}
      <p className="workspace-muted">
        An error or timeout does not prove a refund failed. Refresh saved status
        and reconcile the existing request before attempting another action.
      </p>
      <button
        className="calculator-secondary"
        disabled={action.busy}
        onClick={() => {
          resource.reload()
          onUpdated()
        }}
      >
        Refresh refund & order status
      </button>
    </section>
  )
}
