import { HistorySelection } from '../../components/HistorySelection'
import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { Field, TextArea } from '../../components/FormFields'
import { ErrorNotice } from '../../components/Feedback'
import { useAction } from '../../hooks/useAction'
import { useResource } from '../../hooks/useResource'
import {
  createComparison,
  createObservation,
  getComparison,
  getComparisons,
  getObservations,
} from '../../services/comparisons'
import type { SellerProduct } from '../../services/seller'
import { fieldValue } from '../../utils/form'
import { usd } from '../../utils/presentation'
import { comparisonUnits, sourceKinds } from '../../types/contracts'
import { choice } from '../../services/decode'

export function ComparisonStep({ product }: { product: SellerProduct }) {
  const resource = useResource(
    useCallback(
      async (signal) => {
        const [observations, reports] = await Promise.all([
          getObservations(product.id, signal),
          getComparisons(product.id, signal),
        ])
        return { observations, reports }
      },
      [product.id],
    ),
  )
  const action = useAction()
  const [report, setReport] = useState<Awaited<
    ReturnType<typeof createComparison>
  > | null>(null)
  const [today] = useState(() => new Date().toISOString().slice(0, 10))

  function addObservation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const fields = new FormData(form)
    void action.run(async () => {
      await createObservation(product.id, {
        label: fieldValue(fields, 'observation-label'),
        product_type: product.product_type,
        currency: 'USD',
        price: fieldValue(fields, 'observation-price'),
        quantity: {
          value: fieldValue(fields, 'observation-quantity'),
          unit: choice(fieldValue(fields, 'observation-unit'), comparisonUnits),
        },
        source: {
          name: fieldValue(fields, 'source-name'),
          kind: choice(fieldValue(fields, 'source-kind'), sourceKinds),
          reference: fieldValue(fields, 'source-reference'),
        },
        location: fieldValue(fields, 'observation-location'),
        observed_on: fieldValue(fields, 'observation-date'),
        quality_notes: fieldValue(fields, 'quality-notes') || null,
      })
      form.reset()
      resource.reload()
    }, 'Observation saved as seller-reported, unverified evidence.')
  }

  function compare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    void action.run(async () => {
      const ids = fields.getAll('observation-id').map(String)
      if (!ids.length)
        throw new Error('Select at least one observation to compare.')
      setReport(
        await createComparison(product.id, {
          observation_ids: ids,
          target_quantity: {
            value: fieldValue(fields, 'comparison-quantity'),
            unit: choice(
              fieldValue(fields, 'comparison-unit'),
              comparisonUnits,
            ),
          },
          max_age_days: Number(fieldValue(fields, 'comparison-age')),
        }),
      )
      resource.reload()
    }, 'Comparison saved. It describes selected evidence, not a recommended selling price.')
  }

  return (
    <section className="workspace-panel">
      <p className="eyebrow">Optional local context</p>
      <h2>Compare with evidence.</h2>
      <p>
        Record prices you actually observed, with a source, date and quantity.
        FairMade does not discover prices or certify equivalent quality. Reports
        normalize only supported units and show stale or incompatible evidence
        explicitly.
      </p>
      <ErrorNotice error={resource.error || action.error} />
      {action.notice && (
        <p className="calculator-notice" role="status">
          {action.notice}
        </p>
      )}
      <details>
        <summary>Add a finished-product price observation</summary>
        <form onSubmit={addObservation}>
          <fieldset className="calculator-form" disabled={action.busy}>
            <legend className="sr-only">Price observation</legend>
            <div className="calculator-grid">
              <Field
                name="observation-label"
                title="Observed product label"
                required
                maxLength={200}
                pattern=".*\S.*"
              />
              <Field
                name="observation-price"
                title="Observed price (USD)"
                type="number"
                min="0"
                max="1000000000"
                step="0.000001"
                required
              />
              <Field
                name="observation-quantity"
                title="Quantity that price buys"
                type="number"
                min="0.000001"
                max="1000000000"
                step="0.000001"
                required
              />
              <label className="calculator-field">
                Quantity unit
                <select name="observation-unit">
                  {['g', 'kg', 'egg', 'dozen', 'loaf', 'item'].map((unit) => (
                    <option key={unit}>{unit}</option>
                  ))}
                </select>
              </label>
              <Field
                name="source-name"
                title="Source name"
                required
                maxLength={200}
                pattern=".*\S.*"
              />
              <label className="calculator-field">
                Source type
                <select name="source-kind">
                  <option value="website">Website</option>
                  <option value="in_person">In person</option>
                  <option value="document">Document</option>
                  <option value="other">Other</option>
                </select>
              </label>
              <Field
                name="source-reference"
                title="Source reference (stored, not fetched)"
                required
                maxLength={2000}
                pattern=".*\S.*"
              />
              <Field
                name="observation-location"
                title="Observed location"
                required
                maxLength={200}
                pattern=".*\S.*"
              />
              <Field
                name="observation-date"
                title="Observed on"
                type="date"
                max={today}
                required
              />
              <TextArea
                name="quality-notes"
                title="Quality notes and uncertainty (optional)"
                maxLength={2000}
              />
            </div>
            <div className="workspace-actions">
              <button className="button-primary" type="submit">
                Save observation
              </button>
            </div>
          </fieldset>
        </form>
      </details>
      {resource.loading && <p role="status">Loading comparison evidence…</p>}
      {resource.data && (
        <>
          <h3>Select observations</h3>
          {!resource.data.observations.items.length ? (
            <p>No observed local prices have been recorded.</p>
          ) : (
            <form onSubmit={compare}>
              <fieldset className="calculator-form" disabled={action.busy}>
                <legend className="sr-only">Build comparison</legend>
                <HistorySelection disabled={action.busy} productId={product.id} kind="price-observations" title="Price observations" name="observation-id" multiple />
                <div className="calculator-grid">
                  <Field
                    name="comparison-quantity"
                    title="Normalize to quantity"
                    type="number"
                    min="0.000001"
                    max="1000000000"
                    step="0.000001"
                    required
                  />
                  <label className="calculator-field">
                    Target unit
                    <select name="comparison-unit">
                      {['g', 'kg', 'egg', 'dozen', 'loaf', 'item'].map(
                        (unit) => (
                          <option key={unit}>{unit}</option>
                        ),
                      )}
                    </select>
                  </label>
                  <Field
                    name="comparison-age"
                    title="Maximum observation age (days)"
                    type="number"
                    min="0"
                    max="365"
                    step="1"
                    required
                    defaultValue="30"
                  />
                </div>
                <div className="workspace-actions">
                  <button className="button-primary" type="submit">
                    Compare & save report
                  </button>
                </div>
              </fieldset>
            </form>
          )}
          <HistorySelection disabled={action.busy} productId={product.id} kind="price-comparisons" title="Comparison reports" value={report?.id ?? ''} onSelect={(id) => {

                if (id)
                  void action.run(async () =>
                    setReport(await getComparison(product.id, id)),
                  )
                else setReport(null)
              }} />
        </>
      )}
      {report && (
        <section className="calculator-notice" aria-label="Comparison report">
          <h3>Selected price context</h3>
          <p>
            As of {report.as_of_date}, per {report.quantity.value}{' '}
            {report.quantity.unit}.
          </p>
          <p>
            Included: {report.included_count}; excluded: {report.excluded_count}
            .
          </p>
          {report.minimum !== null && report.maximum !== null ? (
            <p>
              Descriptive range: {usd(report.minimum)} – {usd(report.maximum)}.
              This is not an objective fairness verdict.
            </p>
          ) : (
            <p>No comparable price range could be established.</p>
          )}
          <ul>
            {report.rows.map((row) => (
              <li key={row.id}>
                <strong>{row.label}</strong>:{' '}
                {row.normalized_price === null
                  ? 'Not convertible'
                  : usd(row.normalized_price)}{' '}
                · {row.included ? 'Included' : 'Excluded'}
                {row.stale ? ' · Stale' : ''}
                <br />
                {row.location} · {row.observed_on} · {row.source} ·{' '}
                {row.reference}
                <br />
                {row.exclusion_reasons.join(', ')}
              </li>
            ))}
          </ul>
          <ul>
            {report.warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        </section>
      )}
      <div className="workspace-actions">
        <button className="calculator-secondary" onClick={resource.reload}>
          Refresh comparison sources
        </button>
      </div>
    </section>
  )
}
