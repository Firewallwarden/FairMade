import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { ErrorNotice, SignInPrompt } from '../components/Feedback'
import { Field } from '../components/FormFields'
import { EvidenceDetails } from '../components/EvidenceDetails'
import { useResource } from '../hooks/useResource'
import { useAction } from '../hooks/useAction'
import { useSession } from '../services/session'
import {
  approveReceipt,
  discardReceipt,
  editReceipt,
  encodeReceiptImage,
  getExpenses,
  getReceipt,
  getReceipts,
  importReceipt,
} from '../services/receipts'
import {
  expenseCategories,
  receiptBlockerLabels,
} from '../services/receipt-contract'
import type { ExpenseDetails } from '../services/receipt-contract'
import { choice } from '../services/decode'
import { fieldValue } from '../utils/form'
import { usd } from '../utils/presentation'

export function ReceiptsPage({ id }: { id?: string }) {
  const session = useSession()
  return (
    <WorkspaceLayout
      title="A clearer record of what goes in."
      intro="Private receipt drafts and seller-reviewed expenses. Extraction is a starting point, not verification."
    >
      {!session ? (
        <SignInPrompt />
      ) : !session.account.roles.includes('seller') ? (
        <p>Approved seller access is required.</p>
      ) : id ? (
        <ReceiptEditor id={id} />
      ) : (
        <ReceiptWorkspace />
      )}
    </WorkspaceLayout>
  )
}

function ReceiptWorkspace() {
  const [tab, setTab] = useState<'drafts' | 'expenses'>('drafts')
  const [offset, setOffset] = useState(0)
  const drafts = useResource(
    useCallback((signal) => getReceipts(offset, signal), [offset]),
  )
  const expenses = useResource(
    useCallback((signal) => getExpenses(offset, signal), [offset]),
  )
  const action = useAction()
  const [attempt, setAttempt] = useState<{
    request_id: string
    image_base64: string
    name: string
  } | null>(null)
  function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const file = new FormData(event.currentTarget).get('receipt-image')
    void action.run(async () => {
      let request = attempt
      if (!request) {
        if (!(file instanceof File)) throw new Error('Choose a receipt image.')
        request = {
          request_id: crypto.randomUUID(),
          image_base64: await encodeReceiptImage(file),
          name: file.name,
        }
        setAttempt(request)
      }
      const draft = await importReceipt({
        request_id: request.request_id,
        image_base64: request.image_base64,
      })
      setAttempt(null)
      window.location.hash = `/receipts/${draft.id}`
    })
  }
  const current = tab === 'drafts' ? drafts : expenses
  return (
    <>
      <a href="#/seller">← Seller workspace</a>
      <section className="workspace-panel">
        <h2>Scan, review, then record.</h2>
        <p>
          Upload a PNG/JPEG up to 5 MiB. Local OCR and AI extract a private
          draft. Check every field before approval. Images are not retained by
          the receipt workflow; payment-line redaction is best effort. Use only
          relevant, nonsensitive receipts.
        </p>
        <ErrorNotice error={action.error} />
        <form onSubmit={upload}>
          <fieldset className="calculator-form" disabled={action.busy}>
            <legend className="sr-only">Import receipt</legend>
            {attempt ? (
              <p>
                Retrying the same image: {attempt.name}. The same request
                identifier is retained.
              </p>
            ) : (
              <label className="calculator-field">
                Receipt image
                <input
                  type="file"
                  name="receipt-image"
                  accept="image/png,image/jpeg"
                  required
                />
              </label>
            )}
            <div className="workspace-actions">
              <button type="submit" className="button-primary">
                {action.busy
                  ? 'Reading receipt…'
                  : attempt
                    ? 'Retry same receipt'
                    : 'Extract private draft'}
              </button>
            </div>
          </fieldset>
        </form>
        {action.busy && (
          <p role="status">
            The local model may take up to a few minutes. No expense is created
            during extraction.
          </p>
        )}
        {attempt && !action.busy && (
          <>
            <p>
              After an uncertain result, check saved drafts before starting
              another import. Reload/sign-in restores saved drafts, but not the
              current image or retry key.
            </p>
            <button
              className="calculator-secondary"
              onClick={() => {
                setAttempt(null)
                drafts.reload()
              }}
            >
              Check drafts & choose another image
            </button>
          </>
        )}
      </section>
      <div className="workspace-actions" aria-label="Receipt records">
        <button
          className="calculator-secondary"
          aria-pressed={tab === 'drafts'}
          onClick={() => {
            setTab('drafts')
            setOffset(0)
          }}
        >
          Saved receipt drafts
        </button>
        <button
          className="calculator-secondary"
          aria-pressed={tab === 'expenses'}
          onClick={() => {
            setTab('expenses')
            setOffset(0)
          }}
        >
          Recorded expenses
        </button>
      </div>
      <ErrorNotice error={current.error} />
      {current.loading && <p role="status">Loading private records…</p>}
      {tab === 'drafts' && drafts.data && (
        <div className="workspace-grid">
          {drafts.data.items.map((draft) => (
            <article className="workspace-panel" key={draft.id}>
              <p className="workspace-status">{draft.state}</p>
              <h2>{draft.details.merchant ?? 'Merchant not identified'}</h2>
              <p>
                {draft.details.purchased_on ?? 'Date unknown'} ·{' '}
                {draft.details.total === null
                  ? 'Total unknown'
                  : draft.details.currency === null
                    ? `${draft.details.total} (currency unconfirmed)`
                    : usd(draft.details.total)}
              </p>
              <p>
                {draft.approval_blockers.length} field/reconciliation issue(s)
                to review.
              </p>
              <a href={`#/receipts/${draft.id}`}>Review saved receipt</a>
            </article>
          ))}
        </div>
      )}
      {tab === 'expenses' && expenses.data && (
        <div className="workspace-grid">
          {expenses.data.items.map((expense) => (
            <article className="workspace-panel" key={expense.id}>
              <p className="eyebrow">Seller-reviewed · Unverified</p>
              <h2>{expense.details.merchant}</h2>
              <p>
                {expense.details.purchased_on} · {expense.details.category}
              </p>
              <p>
                <strong>
                  {expense.details.total === null
                    ? 'Unknown'
                    : usd(expense.details.total)}
                </strong>
              </p>
              <a href={`#/receipts/${expense.receipt_id}`}>
                View source review
              </a>
              <details>
                <summary>Recorded details</summary>
                <EvidenceDetails value={expense.details} />
              </details>
            </article>
          ))}
        </div>
      )}
      {current.data && !current.data.items.length && (
        <div className="workspace-empty">
          No {tab === 'drafts' ? 'receipt drafts' : 'recorded expenses'} on this
          page.
        </div>
      )}
      <div className="workspace-actions">
        <button
          className="calculator-secondary"
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 20))}
        >
          Previous records
        </button>
        <button
          className="calculator-secondary"
          disabled={(current.data?.items.length ?? 0) < 20}
          onClick={() => setOffset(offset + 20)}
        >
          Next records
        </button>
        <button
          className="calculator-secondary"
          onClick={() => {
            drafts.reload()
            expenses.reload()
          }}
        >
          Reload records
        </button>
      </div>
    </>
  )
}

function ReceiptEditor({ id }: { id: string }) {
  const resource = useResource(
    useCallback((signal) => getReceipt(id, signal), [id]),
  )
  return (
    <>
      <a href="#/receipts">← Receipts and expenses</a>
      <ErrorNotice error={resource.error} />
      {resource.loading && <p role="status">Loading saved receipt…</p>}
      {resource.data && (
        <ReceiptReview
          key={`${resource.data.id}-${resource.data.revision}-${resource.data.state}`}
          draft={resource.data}
          onChanged={resource.reload}
        />
      )}
      <button className="calculator-secondary" onClick={resource.reload}>
        Reload saved version
      </button>
    </>
  )
}

function ReceiptReview({
  draft,
  onChanged,
}: {
  draft: Awaited<ReturnType<typeof getReceipt>>
  onChanged: () => void
}) {
  const action = useAction()
  const [dirty, setDirty] = useState(false)
  const [approved, setApproved] = useState(false)
  const [rows, setRows] = useState(() =>
    draft.details.items.map((item) => ({ ...item, key: crypto.randomUUID() })),
  )
  const editable = draft.state === 'draft'
  function changed() {
    setDirty(true)
    setApproved(false)
  }
  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    const value = (name: string) => fieldValue(fields, name) || null
    const details: ExpenseDetails = {
      merchant: value('receipt-merchant'),
      purchased_on: value('receipt-date'),
      currency: value('receipt-currency') === 'USD' ? 'USD' : null,
      subtotal: value('receipt-subtotal'),
      tax: value('receipt-tax'),
      total: value('receipt-total'),
      category: choice(
        fieldValue(fields, 'receipt-category'),
        expenseCategories,
      ),
      items: rows.map((row) => ({
        description: fieldValue(fields, `receipt-item-${row.key}`),
        line_total: value(`receipt-amount-${row.key}`),
      })),
    }
    void action.run(async () => {
      await editReceipt(draft.id, draft.revision, details)
      onChanged()
    })
  }
  return (
    <section className="workspace-panel">
      <p className="eyebrow">
        {draft.state} · Saved revision {draft.revision}
      </p>
      <h2>Review what the receipt actually says.</h2>
      <ErrorNotice error={action.error} />
      <ul>
        {draft.notices.map((notice, index) => (
          <li key={index}>{notice}</li>
        ))}
      </ul>
      <details>
        <summary>Extracted text, fields and provenance</summary>
        <p className="private-instructions">{draft.ocr_text}</p>
        <EvidenceDetails
          value={{ extracted: draft.extracted, provenance: draft.provenance }}
        />
      </details>
      {editable ? (
        <>
          <form onSubmit={save} onChange={changed}>
            <fieldset className="calculator-form" disabled={action.busy}>
              <legend className="sr-only">Correct receipt draft</legend>
              <p>
                Blank amounts stay unknown. Do not replace unreadable values
                with zero. Totals are checked by the backend when you save.
              </p>
              <div className="calculator-grid">
                <Field
                  name="receipt-merchant"
                  title="Merchant (required for approval)"
                  maxLength={200}
                  defaultValue={draft.details.merchant ?? ''}
                />
                <Field
                  name="receipt-date"
                  title="Purchase date (required for approval)"
                  type="date"
                  defaultValue={draft.details.purchased_on ?? ''}
                />
                <label className="calculator-field">
                  Currency (required for approval)
                  <select
                    name="receipt-currency"
                    defaultValue={draft.details.currency ?? ''}
                  >
                    <option value="">Unknown — confirm from receipt</option>
                    <option value="USD">USD</option>
                  </select>
                </label>
                <label className="calculator-field">
                  Expense category
                  <select
                    name="receipt-category"
                    defaultValue={draft.details.category}
                  >
                    {expenseCategories.map((category) => (
                      <option key={category}>{category}</option>
                    ))}
                  </select>
                </label>
                {(['subtotal', 'tax', 'total'] as const).map((name) => (
                  <Field
                    key={name}
                    name={`receipt-${name}`}
                    title={
                      name === 'total'
                        ? 'Total USD (required for approval)'
                        : `${name} USD (blank = unknown)`
                    }
                    type="number"
                    min="0"
                    max="1000000000"
                    step="0.01"
                    defaultValue={draft.details[name] ?? ''}
                  />
                ))}
              </div>
              <h3>Line items</h3>
              {rows.map((row, index) => (
                <div className="calculator-grid" key={row.key}>
                  <Field
                    name={`receipt-item-${row.key}`}
                    title={`Item ${index + 1} description`}
                    required
                    maxLength={200}
                    defaultValue={row.description}
                  />
                  <Field
                    name={`receipt-amount-${row.key}`}
                    title={`Item ${index + 1} total USD (blank = unknown)`}
                    type="number"
                    min="0"
                    max="1000000000"
                    step="0.01"
                    defaultValue={row.line_total ?? ''}
                  />
                  <button
                    type="button"
                    className="calculator-remove"
                    onClick={() => {
                      setRows(rows.filter((item) => item.key !== row.key))
                      changed()
                    }}
                  >
                    Remove item {index + 1}
                  </button>
                </div>
              ))}
              <div className="workspace-actions">
                <button
                  type="button"
                  className="calculator-secondary"
                  disabled={rows.length >= 50}
                  onClick={() => {
                    setRows([
                      ...rows,
                      {
                        key: crypto.randomUUID(),
                        description: '',
                        line_total: null,
                      },
                    ])
                    changed()
                  }}
                >
                  Add line item
                </button>
                <button
                  type="submit"
                  className="button-primary"
                  disabled={!dirty}
                >
                  Save corrections & preview
                </button>
              </div>
            </fieldset>
          </form>
        </>
      ) : (
        <p className="calculator-notice">
          This receipt was approved. Its recorded expense is retained privately;
          it does not update inventory, pricing or public disclosures.
        </p>
      )}
      <section aria-label="Exact saved expense preview">
        <h3>Exact saved expense preview</h3>
        <EvidenceDetails value={draft.details} />
        {draft.approval_blockers.length > 0 && (
          <div className="calculator-notice">
            <strong>Resolve before approval</strong>
            <ul>
              {draft.approval_blockers.map((code) => (
                <li key={code}>
                  {receiptBlockerLabels[code] ?? code.replaceAll('_', ' ')}
                </li>
              ))}
            </ul>
          </div>
        )}
        {dirty && (
          <p role="status">
            Unsaved edits are not part of this preview. Save corrections before
            approving.
          </p>
        )}
        {editable && (
          <form
            onSubmit={(event) => {
              event.preventDefault()
              if (!approved || dirty || draft.approval_blockers.length) return
              void action.run(async () => {
                await approveReceipt(
                  draft.id,
                  draft.revision,
                  draft.preview_hash,
                )
                onChanged()
              })
            }}
          >
            <label className="workspace-check">
              <input
                name="approve-receipt"
                type="checkbox"
                required
                checked={approved}
                disabled={
                  dirty || action.busy || draft.approval_blockers.length > 0
                }
                onChange={(event) => setApproved(event.target.checked)}
              />
              I reviewed the exact saved merchant, date, items, category and
              amounts above, and approve recording this private expense.
            </label>
            <div className="workspace-actions">
              <button
                className="button-primary"
                disabled={
                  !approved ||
                  dirty ||
                  action.busy ||
                  draft.approval_blockers.length > 0
                }
              >
                Approve & record expense
              </button>
            </div>
          </form>
        )}
      </section>
      {editable && (
        <details>
          <summary>Discard unapproved draft</summary>
          <form
            onSubmit={(event) => {
              event.preventDefault()
              if (new FormData(event.currentTarget).has('discard-receipt'))
                void action.run(async () => {
                  await discardReceipt(draft.id)
                  window.location.hash = '/receipts'
                })
            }}
          >
            <label className="workspace-check">
              <input
                type="checkbox"
                name="discard-receipt"
                required
                disabled={action.busy}
              />
              Delete this unapproved draft and its extracted text.
            </label>
            <button className="calculator-secondary" disabled={action.busy}>
              Discard draft
            </button>
          </form>
        </details>
      )}
    </section>
  )
}
