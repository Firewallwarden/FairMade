import { useCallback, useEffect, useRef, useState } from 'react'
import {
  captureCheckout,
  createCheckout,
  getPayPalConfig,
} from '../services/commerce'
import { loadPayPal } from '../services/paypal-sdk'
import { ErrorNotice } from './Feedback'
import { useResource } from '../hooks/useResource'

export function PayPalCheckout({
  orderId,
  onUpdated,
}: {
  orderId: string
  onUpdated: () => void
}) {
  const config = useResource(
    useCallback((signal) => getPayPalConfig(signal), []),
  )
  const [error, setError] = useState<unknown>(null)
  const [notice, setNotice] = useState('')
  const [version, setVersion] = useState(0)
  const [busy, setBusy] = useState(false)
  const container = useRef<HTMLDivElement>(null)
  const clientId = config.data?.enabled ? config.data.client_id : null

  useEffect(() => {
    if (!clientId || !container.current) return
    let active = true
    let buttons:
      | ReturnType<Awaited<ReturnType<typeof loadPayPal>>['Buttons']>
      | undefined
    const target = container.current
    loadPayPal(clientId)
      .then(async (sdk) => {
        if (!active) return
        buttons = sdk.Buttons({
          style: { layout: 'vertical', label: 'paypal', shape: 'pill' },
          createOrder: async () => {
            setError(null)
            setNotice('Creating sandbox checkout with the backend…')
            setBusy(true)
            try {
              const checkout = await createCheckout(orderId)
              if (checkout.state !== 'ready' || !checkout.provider_order_id) {
                onUpdated()
                throw new Error(
                  'Checkout is not ready for approval. Refresh the saved status before trying again.',
                )
              }
              return checkout.provider_order_id
            } catch (error) {
              if (active) setError(error)
              throw error
            } finally {
              if (active) setBusy(false)
            }
          },
          onApprove: async () => {
            setBusy(true)
            setNotice(
              'Approval received. Waiting for backend payment verification…',
            )
            try {
              await captureCheckout(orderId)
              onUpdated()
            } catch (error) {
              if (active) {
                setError(error)
                setNotice(
                  'Payment is not confirmed. Refresh the saved status and use Verify with PayPal to recover before attempting another payment.',
                )
              }
            } finally {
              if (active) setBusy(false)
            }
          },
          onCancel: () => {
            if (active)
              setNotice(
                'The approval window was closed. This does not confirm payment or cancel your FairMade order. Refresh the saved status before continuing.',
              )
          },
          onError: () => {
            if (active) {
              setBusy(false)
              setError(
                new Error(
                  'Checkout could not finish. No payment is confirmed here. Check the saved status before trying again.',
                ),
              )
            }
          },
        })
        if (!buttons.isEligible())
          throw new Error(
            'PayPal is not available in this browser. Try another supported browser.',
          )
        await buttons.render(target)
      })
      .catch((error) => {
        if (active) setError(error)
      })
    return () => {
      active = false
      void buttons?.close().catch(() => {})
    }
  }, [clientId, orderId, onUpdated, version])

  return (
    <section className="workspace-panel">
      <h2>PayPal sandbox checkout</h2>
      <p>
        This is a shared sandbox merchant demo. No live payment or seller payout
        is supported.
      </p>
      <ErrorNotice error={config.error || error} />
      {config.loading && <p role="status">Checking sandbox availability…</p>}
      {config.data && !config.data.enabled && (
        <p className="calculator-notice">
          PayPal sandbox is not configured on the backend. Your order is not
          paid. The backend owner must configure sandbox credentials before a
          purchase can be completed.
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {clientId && (
        <div
          ref={container}
          className="paypal-container"
          aria-label="PayPal sandbox payment buttons"
          aria-busy={busy}
        />
      )}
      {Boolean(config.error) && (
        <button className="calculator-secondary" onClick={config.reload}>
          Retry configuration
        </button>
      )}
      {Boolean(error) && clientId && (
        <button
          className="calculator-secondary"
          disabled={busy}
          onClick={() => {
            setError(null)
            setVersion(version + 1)
          }}
        >
          Reload payment interface
        </button>
      )}
    </section>
  )
}
