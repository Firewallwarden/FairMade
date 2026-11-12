import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { Field, TextArea } from '../../components/FormFields'
import { BatchEntries } from '../../components/BatchEntries'
import { ErrorNotice } from '../../components/Feedback'
import { EvidenceDetails } from '../../components/EvidenceDetails'
import { useResource } from '../../hooks/useResource'
import { useAction } from '../../hooks/useAction'
import {
  getProductionRecords,
  getProductionRecord,
  createProductionRecord,
} from '../../services/production'
import type { ProductionInput } from '../../services/production-contract'
import type { SellerProduct } from '../../services/seller'
import { choice } from '../../services/decode'
import { ApiError } from '../../services/http'
import { fieldValue } from '../../utils/form'
import { readBatchEntries } from '../../utils/batch-entries'
import { usd } from '../../utils/presentation'

export function ProductionStep({ product }: { product: SellerProduct }) {
  const [offset, setOffset] = useState(0),
    [includeCorrected, setIncludeCorrected] = useState(false)
  const resource = useResource(
    useCallback(
      (signal) =>
        getProductionRecords(product.id, offset, includeCorrected, signal),
      [product.id, offset, includeCorrected],
    ),
  )
  const [selected, setSelected] = useState<Awaited<
    ReturnType<typeof getProductionRecord>
  > | null>(null)
  const action = useAction()
  return (
    <section className="workspace-panel">
      <h2>What did this batch actually yield?</h2>
      <p>
        Record completed batches or production periods, usable output and
        reported costs. This does not update the recipe, materials, listing
        stock, prices or public disclosures. Zero sellable yield keeps unit cost
        unknown.
      </p>
      <ErrorNotice error={resource.error || action.error} />
      {resource.loading && (
        <p role="status">Loading completed production records…</p>
      )}
      {resource.data && (
        <ProductionForm
          product={product}
          records={resource.data.items}
          onSaved={(record) => {
            setSelected(record)
            resource.reload()
          }}
        />
      )}
      <label className="workspace-check">
        <input
          type="checkbox"
          checked={includeCorrected}
          onChange={(event) => {
            setIncludeCorrected(event.target.checked)
            setOffset(0)
          }}
        />
        Also show historical records that were corrected.
      </label>
      {resource.data && !resource.data.items.length && (
        <p>No completed records on this page.</p>
      )}
      {resource.data?.items.map((record) => (
        <article className="workspace-panel" key={record.id}>
          <h3>{record.label}</h3>
          <p>
            {record.started_on} – {record.completed_on} ·{' '}
            {record.sellable_units} sellable of {record.total_units} total{' '}
            {record.selling_unit} units.
          </p>
          {record.corrects_record_id && (
            <p>
              This record corrects an earlier report; the earlier snapshot is
              retained.
            </p>
          )}
          <button
            className="calculator-secondary"
            disabled={action.busy}
            onClick={() =>
              action.run(async () =>
                setSelected(await getProductionRecord(product.id, record.id)),
              )
            }
          >
            Review production snapshot
          </button>
        </article>
      ))}
      {selected && (
        <section
          className="calculator-notice"
          aria-label="Saved production result"
        >
          <h3>{selected.label}</h3>
          <p>
            Backend-modeled batch total: {usd(selected.result.batch_total)}.
            Modeled cost per sellable {selected.selling_unit}:{' '}
            {selected.result.unit_cost === null
              ? 'Unknown — no sellable yield'
              : usd(selected.result.unit_cost)}
            .
          </p>
          <p>
            Unsellable output: {selected.result.unsellable_units}. Yield
            fraction: {selected.result.yield_fraction ?? 'Unknown'} (1 = all
            output sellable).
          </p>
          <ul>
            {selected.result.warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
          <details>
            <summary>Exact reported inputs and source snapshots</summary>
            <EvidenceDetails
              value={{
                product: selected.snapshot,
                reported: selected.request,
                livestock: selected.livestock_snapshot,
                category_totals: selected.result.category_totals,
              }}
            />
          </details>
        </section>
      )}
      <div className="workspace-actions">
        <button
          className="calculator-secondary"
          disabled={!offset}
          onClick={() => setOffset(offset - 20)}
        >
          Previous production records
        </button>
        <button
          className="calculator-secondary"
          disabled={(resource.data?.items.length ?? 0) < 20}
          onClick={() => setOffset(offset + 20)}
        >
          Next production records
        </button>
        <button className="calculator-secondary" onClick={resource.reload}>
          Reload saved production
        </button>
      </div>
    </section>
  )
}
function ProductionForm({
  product,
  records,
  onSaved,
}: {
  product: SellerProduct
  records: Awaited<ReturnType<typeof getProductionRecords>>['items']
  onSaved: (record: Awaited<ReturnType<typeof createProductionRecord>>) => void
}) {
  const action = useAction(),
    [attempt, setAttempt] = useState<ProductionInput | null>(null),
    [corrects, setCorrects] = useState('')
  const [today] = useState(() => new Date().toISOString().slice(0, 10))
  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    void action.run(async () => {
      const batch = readBatchEntries(fields, 'production')
      const request: ProductionInput = attempt ?? {
        request_id: crypto.randomUUID(),
        label: fieldValue(fields, 'production-label'),
        kind: choice(fieldValue(fields, 'production-kind'), [
          'batch',
          'production_period',
        ] as const),
        started_on: fieldValue(fields, 'production-started'),
        completed_on: fieldValue(fields, 'production-completed'),
        selling_unit: product.selling_unit,
        total_units: Number(fieldValue(fields, 'production-total')),
        sellable_units: Number(fieldValue(fields, 'production-sellable')),
        currency: 'USD',
        costs: batch.costs,
        labor: batch.labor,
        notes: fieldValue(fields, 'production-notes') || null,
        corrects_record_id: corrects || null,
        correction_reason: corrects
          ? fieldValue(fields, 'production-correction-reason')
          : null,
        livestock_source: null,
      }
      if (request.sellable_units > request.total_units)
        throw new Error('Sellable output cannot exceed total output.')
      setAttempt(request)
      try {
        const saved = await createProductionRecord(product.id, request)
        setAttempt(null)
        onSaved(saved)
      } catch (error) {
        if (error instanceof ApiError && error.status === 422) setAttempt(null)
        throw error
      }
    })
  }
  return (
    <details open>
      <summary>Record a completed batch or period</summary>
      <ErrorNotice error={action.error} />
      <form onSubmit={save}>
        <fieldset
          className="calculator-form"
          disabled={action.busy || Boolean(attempt)}
        >
          <legend className="sr-only">Completed production inputs</legend>
          <div className="calculator-grid">
            <Field
              name="production-label"
              title="Completed report label"
              required
              maxLength={200}
            />
            <label className="calculator-field">
              Report type
              <select name="production-kind">
                <option value="batch">Completed batch</option>
                <option value="production_period">
                  Completed production period
                </option>
              </select>
            </label>
            <Field
              name="production-started"
              title="Started on"
              type="date"
              max={today}
              required
            />
            <Field
              name="production-completed"
              title="Completed on"
              type="date"
              max={today}
              required
            />
            <Field
              name="production-total"
              title={`Total ${product.selling_unit} output units`}
              type="number"
              min="0"
              max="1000000"
              step="1"
              required
            />
            <Field
              name="production-sellable"
              title="Sellable output units"
              type="number"
              min="0"
              max="1000000"
              step="1"
              required
            />
            <label className="calculator-field">
              Correct an earlier record (latest page)
              <select
                value={corrects}
                onChange={(event) => setCorrects(event.target.value)}
              >
                <option value="">New completed report</option>
                {records.map((record) => (
                  <option key={record.id} value={record.id}>
                    {record.completed_on} · {record.label}
                  </option>
                ))}
              </select>
            </label>
            {corrects && (
              <TextArea
                name="production-correction-reason"
                title="Correction reason"
                required
                maxLength={2000}
              />
            )}
          </div>
          <BatchEntries prefix="production" costLimit={200} />
          <TextArea
            name="production-notes"
            title="Private report notes (optional)"
            maxLength={2000}
          />
        </fieldset>
        <div className="workspace-actions">
          <button className="button-primary" disabled={action.busy}>
            {attempt
              ? 'Retry same completed report'
              : 'Save completed production report'}
          </button>
        </div>
      </form>
      {attempt && (
        <p>
          The exact payload and retry identifier are retained. Check saved
          history after a timeout or conflict before starting another report.
        </p>
      )}
    </details>
  )
}
