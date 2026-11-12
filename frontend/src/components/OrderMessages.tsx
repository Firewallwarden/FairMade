import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { getMessages, sendMessage } from '../services/order-care'
import { useResource } from '../hooks/useResource'
import { useAction } from '../hooks/useAction'
import { ErrorNotice } from './Feedback'
import { TextArea } from './FormFields'
import { fieldValue } from '../utils/form'

export function OrderMessages({ orderId }: { orderId: string }) {
  const [cursor, setCursor] = useState(0)
  const resource = useResource(
    useCallback(
      (signal) => getMessages(orderId, cursor, signal),
      [orderId, cursor],
    ),
  )
  const action = useAction()
  const [attempt, setAttempt] = useState<{
    request_id: string
    text: string
  } | null>(null)
  function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const request = attempt ?? {
      request_id: crypto.randomUUID(),
      text: fieldValue(new FormData(form), 'order-message'),
    }
    setAttempt(request)
    void action.run(async () => {
      const saved = await sendMessage(orderId, request)
      setAttempt(null)
      form.reset()
      setCursor(Math.max(0, saved.sequence - 20))
      resource.reload()
    }, 'Message saved to this private order conversation.')
  }
  return (
    <section className="workspace-panel">
      <h2>A word with your neighbor.</h2>
      <p>
        Private to this order’s buyer and seller. Plain text only; messages do
        not change payment, refunds or pickup state. Messages remain in the
        order history.
      </p>
      <ErrorNotice error={resource.error || action.error} />
      {action.notice && <p role="status">{action.notice}</p>}
      {resource.loading && <p role="status">Loading private messages…</p>}
      {resource.data && (
        <>
          {!resource.data.items.length && <p>No messages on this page yet.</p>}
          {resource.data.items.map((message) => (
            <article className="message-bubble" key={message.id}>
              <strong>
                {message.is_mine
                  ? 'You'
                  : message.sender === 'seller'
                    ? 'Seller'
                    : 'Buyer'}
              </strong>{' '}
              · {new Date(message.created_at).toLocaleString()}
              <p>{message.text}</p>
            </article>
          ))}
          <div className="workspace-actions">
            <button
              className="calculator-secondary"
              disabled={!cursor || action.busy}
              onClick={() => setCursor(Math.max(0, cursor - 20))}
            >
              Earlier messages
            </button>
            <button
              className="calculator-secondary"
              disabled={!resource.data.has_more || action.busy}
              onClick={() =>
                setCursor(resource.data?.next_after_sequence ?? cursor)
              }
            >
              Later messages
            </button>
          </div>
        </>
      )}
      <form onSubmit={send}>
        <fieldset disabled={action.busy} className="calculator-form">
          <legend className="sr-only">Send order message</legend>
          <TextArea
            name="order-message"
            title="Your message"
            required
            maxLength={2000}
            readOnly={Boolean(attempt)}
          />
          {attempt && (
            <p>
              A retry uses this same message and request identifier to avoid
              duplicates.
            </p>
          )}
          <div className="workspace-actions">
            <button type="submit" className="button-primary">
              {action.busy
                ? 'Sending…'
                : attempt
                  ? 'Retry same message'
                  : 'Send private message'}
            </button>
          </div>
        </fieldset>
      </form>
      <button
        className="calculator-secondary"
        disabled={action.busy}
        onClick={() => {
          setAttempt(null)
          resource.reload()
        }}
      >
        Refresh order conversation
      </button>
    </section>
  )
}
