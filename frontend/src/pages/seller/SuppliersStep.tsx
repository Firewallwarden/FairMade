import { HistorySelection } from '../../components/HistorySelection'
import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import {
  getSourcingInputs,
  getSourcingInput,
  createSourcingInput,
  getSupplierQuotes,
  createSupplierQuote,
  saveInputLocks,
  createSupplierReport,
  getSupplierReports,
  getSupplierReport,
  getSupplierRecommendations,
} from '../../services/suppliers'
import { supplyUnits } from '../../services/supplier-contract'
import type { QualityClaim } from '../../services/quality-contract'
import { getLocks } from '../../services/seller'
import { choice } from '../../services/decode'
import { sourceKinds } from '../../types/contracts'
import { useResource } from '../../hooks/useResource'
import { useAction } from '../../hooks/useAction'
import { Field, TextArea } from '../../components/FormFields'
import { ErrorNotice } from '../../components/Feedback'
import { fieldValue } from '../../utils/form'
import { ruleDescription, usd } from '../../utils/presentation'
import {
  OptionalPreferences,
  AdditionalQuoteClaims,
} from '../../components/OptionalPreferences'
import {
  readAdditionalClaims,
  readOptionalPreferences,
} from '../../utils/optional-preferences'

export function SuppliersStep({ productId }: { productId: string }) {
  const resource = useResource(
    useCallback((signal) => getSourcingInputs(productId, signal), [productId]),
  )
  const [selected, setSelected] = useState('')
  const action = useAction()
  return (
    <section className="workspace-panel">
      <h2>Save thoughtfully. Protect your standards.</h2>
      <p>
        Record actual dated supplier quotes. Input-specific mandatory rules gate
        every comparison. Missing transport, unknown availability, incompatible
        units or failed claims are excluded, not recommended as savings.
      </p>
      <ErrorNotice error={resource.error || action.error} />
      <form
        onSubmit={(event) => {
          event.preventDefault()
          const label = fieldValue(
            new FormData(event.currentTarget),
            'sourcing-label',
          )
          void action.run(async () => {
            const input = await createSourcingInput(productId, label)
            setSelected(input.id)
            resource.reload()
          })
        }}
      >
        <Field
          name="sourcing-label"
          title="Ingredient/material to source"
          required
          maxLength={200}
          placeholder="e.g. bread flour or egg cartons"
        />
        <div className="workspace-actions">
          <button
            className="calculator-secondary"
            type="submit"
            disabled={action.busy}
          >
            Create private sourcing input
          </button>
        </div>
      </form>
      {resource.loading && <p role="status">Loading sourcing inputs…</p>}
      {resource.data && (
        <HistorySelection disabled={action.busy} productId={productId} kind="sourcing-inputs" title="Sourcing inputs" value={selected} onSelect={setSelected} />
      )}
      {selected && (
        <InputWorkspace
          key={selected}
          productId={productId}
          inputId={selected}
        />
      )}
    </section>
  )
}

function InputWorkspace({
  productId,
  inputId,
}: {
  productId: string
  inputId: string
}) {
  const resource = useResource(
    useCallback(
      async (signal) => {
        const [input, quotes, reports] = await Promise.all([
          getSourcingInput(productId, inputId, signal),
          getSupplierQuotes(productId, inputId, signal),
          getSupplierReports(productId, inputId, signal),
        ])
        return { input, quotes, reports }
      },
      [productId, inputId],
    ),
  )
  const action = useAction()
  const [report, setReport] = useState<Awaited<
    ReturnType<typeof createSupplierReport>
  > | null>(null)
  const [recommendations, setRecommendations] = useState<Awaited<
    ReturnType<typeof getSupplierRecommendations>
  > | null>(null)
  const [today] = useState(() => new Date().toISOString().slice(0, 10))

  function addQuote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const fields = new FormData(form)
    const input = resource.data?.input
    if (!input) return
    void action.run(async () => {
      const claims: Record<string, QualityClaim> = {}
      input.rules.forEach((rule) => {
        const value = fieldValue(fields, `supply-claim-${rule.key}`)
        if (value)
          claims[rule.key] =
            rule.type === 'boolean'
              ? { type: 'boolean', value: value === 'true' }
              : rule.type === 'choice'
                ? { type: 'choice', value }
                : { type: 'numeric', value, unit: rule.unit }
      })
      await createSupplierQuote(productId, inputId, {
        supplier_name: fieldValue(fields, 'supplier-name'),
        currency: 'USD',
        package_price: fieldValue(fields, 'package-price'),
        package_quantity: {
          value: fieldValue(fields, 'package-quantity'),
          unit: choice(fieldValue(fields, 'package-unit'), supplyUnits),
        },
        usable_fraction: fieldValue(fields, 'usable-fraction'),
        minimum_packages: Number(fieldValue(fields, 'minimum-packages')),
        maximum_packages: fieldValue(fields, 'maximum-packages')
          ? Number(fieldValue(fields, 'maximum-packages'))
          : null,
        transport_cost: fieldValue(fields, 'transport-cost') || null,
        availability: choice(fieldValue(fields, 'supplier-availability'), [
          'available',
          'unavailable',
          'unknown',
        ] as const),
        source: {
          name: fieldValue(fields, 'supplier-source-name'),
          kind: choice(fieldValue(fields, 'supplier-source-kind'), sourceKinds),
          reference: fieldValue(fields, 'supplier-reference'),
        },
        location: fieldValue(fields, 'supplier-location'),
        observed_on: fieldValue(fields, 'supplier-date'),
        valid_until: fieldValue(fields, 'supplier-expiry') || null,
        claims: readAdditionalClaims(
          fields,
          claims,
          input.rules.map((rule) => rule.key),
        ),
        notes: fieldValue(fields, 'supplier-notes') || null,
      })
      form.reset()
      resource.reload()
    }, 'Unverified supplier quote saved. Source references are stored, not fetched.')
  }
  return (
    <>
      <ErrorNotice error={resource.error || action.error} />
      {action.notice && (
        <p role="status" className="calculator-notice">
          {action.notice}
        </p>
      )}
      {resource.loading && <p role="status">Loading input rules and quotes…</p>}
      {resource.data && (
        <>
          <h3>Mandatory requirements for {resource.data.input.label}</h3>
          {!resource.data.input.rules.length && (
            <p>
              No requirements configured. Empty or unverified checks do not
              establish eligibility.
            </p>
          )}
          <ul>
            {resource.data.input.rules.map((rule) => (
              <li key={rule.key}>
                {rule.label}: {ruleDescription(rule)}{' '}
                <button
                  className="calculator-remove"
                  disabled={action.busy}
                  onClick={() => {
                    const input = resource.data?.input
                    if (input)
                      void action.run(async () => {
                        await saveInputLocks(
                          productId,
                          inputId,
                          input.rule_revision,
                          input.rules.filter((item) => item.key !== rule.key),
                        )
                        resource.reload()
                        setReport(null)
                        setRecommendations(null)
                      })
                  }}
                >
                  Remove requirement
                </button>
              </li>
            ))}
          </ul>
          <details>
            <summary>Add a yes/no input requirement</summary>
            <form
              onSubmit={(event) => {
                event.preventDefault()
                const fields = new FormData(event.currentTarget)
                const input = resource.data?.input
                if (input)
                  void action.run(async () => {
                    await saveInputLocks(
                      productId,
                      inputId,
                      input.rule_revision,
                      [
                        ...input.rules,
                        {
                          key: fieldValue(fields, 'supply-rule-key'),
                          label: fieldValue(fields, 'supply-rule-label'),
                          type: 'boolean',
                          expected:
                            fieldValue(fields, 'supply-rule-value') === 'true',
                        },
                      ],
                    )
                    resource.reload()
                    setReport(null)
                    setRecommendations(null)
                  })
              }}
            >
              <div className="calculator-grid">
                <Field
                  name="supply-rule-label"
                  title="Mandatory requirement"
                  required
                  maxLength={200}
                />
                <Field
                  name="supply-rule-key"
                  title="Unique attribute key"
                  required
                  pattern="[a-z][a-z0-9_]{0,63}"
                  maxLength={64}
                />
                <label className="calculator-field">
                  Required value
                  <select name="supply-rule-value">
                    <option value="true">Yes / true</option>
                    <option value="false">No / false</option>
                  </select>
                </label>
              </div>
              <button
                type="submit"
                className="calculator-secondary"
                disabled={
                  action.busy || resource.data.input.rules.length >= 100
                }
              >
                Save input requirement
              </button>
            </form>
          </details>
          <details>
            <summary>Copy current product requirements deliberately</summary>
            <p>
              Input rules are separate. Copy only if the product rules describe
              this specific ingredient/material. This replaces the input’s
              current rules, including numeric/choice rules.
            </p>
            <form
              onSubmit={(event) => {
                event.preventDefault()
                const input = resource.data?.input
                if (
                  !new FormData(event.currentTarget).has(
                    'confirm-copy-locks',
                  ) ||
                  !input
                )
                  return
                void action.run(async () => {
                  const locks = await getLocks(productId)
                  await saveInputLocks(
                    productId,
                    inputId,
                    input.rule_revision,
                    locks.rules,
                  )
                  resource.reload()
                  setReport(null)
                  setRecommendations(null)
                })
              }}
            >
              <label className="workspace-check">
                <input type="checkbox" name="confirm-copy-locks" required />
                Replace this input’s rules with the current product rules.
              </label>
              <button className="calculator-secondary" disabled={action.busy}>
                Copy requirements
              </button>
            </form>
          </details>
          <details>
            <summary>Add a sourced supplier quote</summary>
            <form onSubmit={addQuote}>
              <fieldset disabled={action.busy} className="calculator-form">
                <legend className="sr-only">Supplier quote</legend>
                <div className="calculator-grid">
                  <Field
                    name="supplier-name"
                    title="Supplier name"
                    required
                    maxLength={200}
                  />
                  <Field
                    name="supplier-location"
                    title="Supplier location"
                    required
                    maxLength={200}
                  />
                  <Field
                    name="package-price"
                    title="Price per package (USD)"
                    type="number"
                    min="0"
                    max="1000000000"
                    step="0.01"
                    required
                  />
                  <Field
                    name="package-quantity"
                    title="Quantity per package"
                    type="number"
                    min="0.000001"
                    max="1000000000"
                    step="0.000001"
                    required
                  />
                  <label className="calculator-field">
                    Package unit
                    <select name="package-unit">
                      {supplyUnits.map((unit) => (
                        <option key={unit}>{unit}</option>
                      ))}
                    </select>
                  </label>
                  <Field
                    name="usable-fraction"
                    title="Usable fraction (1 = 100%, 0.9 = 90%)"
                    type="number"
                    min="0.000001"
                    max="1"
                    step="0.000001"
                    required
                  />
                  <Field
                    name="minimum-packages"
                    title="Minimum packages"
                    type="number"
                    min="1"
                    max="1000000"
                    step="1"
                    required
                    defaultValue="1"
                  />
                  <Field
                    name="maximum-packages"
                    title="Maximum packages (optional)"
                    type="number"
                    min="1"
                    max="1000000"
                    step="1"
                  />
                  <Field
                    name="transport-cost"
                    title="Transport for purchase (USD; blank = unknown, explicit 0 = free)"
                    type="number"
                    min="0"
                    max="1000000000"
                    step="0.01"
                  />
                  <label className="calculator-field">
                    Reported availability
                    <select name="supplier-availability" defaultValue="unknown">
                      <option value="unknown">Unknown</option>
                      <option value="available">Available</option>
                      <option value="unavailable">Unavailable</option>
                    </select>
                  </label>
                  <Field
                    name="supplier-source-name"
                    title="Source name"
                    required
                    maxLength={200}
                  />
                  <label className="calculator-field">
                    Source type
                    <select name="supplier-source-kind">
                      {sourceKinds.map((kind) => (
                        <option key={kind} value={kind}>
                          {kind.replaceAll('_', ' ')}
                        </option>
                      ))}
                    </select>
                  </label>
                  <Field
                    name="supplier-reference"
                    title="Source reference (not fetched)"
                    required
                    maxLength={2000}
                  />
                  <Field
                    name="supplier-date"
                    title="Observed on"
                    type="date"
                    required
                    max={today}
                  />
                  <Field
                    name="supplier-expiry"
                    title="Valid until (optional)"
                    type="date"
                  />
                  <TextArea
                    name="supplier-notes"
                    title="Notes and uncertainty"
                    maxLength={2000}
                  />
                </div>
                <h4>Seller-reported candidate claims</h4>
                <div className="calculator-grid">
                  {resource.data.input.rules.map((rule) => (
                    <label className="calculator-field" key={rule.key}>
                      {rule.label}
                      {rule.type === 'numeric' ? (
                        <input
                          name={`supply-claim-${rule.key}`}
                          type="number"
                          min="-1000000000"
                          max="1000000000"
                          step="0.000001"
                          placeholder={`Unknown, or value in ${rule.unit}`}
                        />
                      ) : (
                        <select name={`supply-claim-${rule.key}`}>
                          <option value="">Unknown / no evidence</option>
                          {rule.type === 'boolean' ? (
                            <>
                              <option value="true">Yes / true</option>
                              <option value="false">No / false</option>
                            </>
                          ) : (
                            rule.allowed_values.map((value) => (
                              <option key={value}>{value}</option>
                            ))
                          )}
                        </select>
                      )}
                    </label>
                  ))}
                </div>
                <AdditionalQuoteClaims />
                <div className="workspace-actions">
                  <button type="submit" className="button-primary">
                    Save private quote
                  </button>
                </div>
              </fieldset>
            </form>
          </details>
          <h3>Choose quotes to compare</h3>
          <form
            onSubmit={(event) => {
              event.preventDefault()
              const fields = new FormData(event.currentTarget)
              const input = resource.data?.input
              if (!input) return
              void action.run(async () => {
                setRecommendations(null)
                setReport(
                  await createSupplierReport(productId, inputId, {
                    quote_ids: fields.getAll('supplier-quote').map(String),
                    expected_rule_revision: input.rule_revision,
                    required_quantity: {
                      value: fieldValue(fields, 'required-supply-quantity'),
                      unit: choice(
                        fieldValue(fields, 'required-supply-unit'),
                        supplyUnits,
                      ),
                    },
                    max_age_days: Number(
                      fieldValue(fields, 'supplier-max-age'),
                    ),
                  }),
                )
                resource.reload()
              })
            }}
          >
            <fieldset
              disabled={action.busy || !resource.data.quotes.items.length}
              className="calculator-form"
            >
              <legend className="sr-only">Compare supplier quotes</legend>
              <HistorySelection disabled={action.busy} productId={productId} kind="supplier-quotes" title="Supplier quotes" inputId={inputId} name="supplier-quote" multiple />
              <div className="calculator-grid">
                <Field
                  name="required-supply-quantity"
                  title="Required usable quantity"
                  type="number"
                  min="0.000001"
                  max="1000000000"
                  step="0.000001"
                  required
                />
                <label className="calculator-field">
                  Required unit
                  <select name="required-supply-unit">
                    {supplyUnits.map((unit) => (
                      <option key={unit}>{unit}</option>
                    ))}
                  </select>
                </label>
                <Field
                  name="supplier-max-age"
                  title="Maximum quote age (days)"
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
                  Compare & save supplier report
                </button>
              </div>
            </fieldset>
          </form>
          <HistorySelection disabled={action.busy} productId={productId} kind="supplier-comparisons" title="Supplier comparison reports" inputId={inputId} value={report?.id ?? ''} onSelect={(id) => {

                setRecommendations(null)
                if (id)
                  void action.run(async () =>
                    setReport(await getSupplierReport(productId, inputId, id)),
                  )
                else setReport(null)
              }} />
        </>
      )}
      {report && (
        <section
          className="calculator-notice"
          aria-label="Supplier comparison report"
        >
          <h3>Supplier cost review</h3>
          <p>
            As of {report.as_of_date}, for {report.quantity.value}{' '}
            {report.quantity.unit}. Eligible quotes: {report.eligible_count}.
            Lowest eligible purchase outlay:{' '}
            {report.lowest_purchase_cost === null
              ? 'Not established'
              : usd(report.lowest_purchase_cost)}
            .
          </p>
          {report.rows.map((row) => (
            <article key={row.quote_id}>
              <h4>
                {row.supplier_name}:{' '}
                {row.eligible
                  ? 'Eligible for input cost review'
                  : 'Excluded — not an acceptable saving'}
              </h4>
              <p>
                Quality claim check: {row.quality}.{' '}
                {row.reasons.join(', ').replaceAll('_', ' ')}
              </p>
              {row.cost && (
                <p>
                  {row.cost.packages} packages · Total outlay{' '}
                  {usd(row.cost.purchase_cost)} including transport{' '}
                  {usd(row.cost.transport)} · {usd(row.cost.unit_cost)} per
                  usable {report.quantity.unit}.{' '}
                  {row.eligible
                    ? ''
                    : 'Shown for context only; excluded from eligible minima.'}
                </p>
              )}
            </article>
          ))}
          <ul>
            {report.warnings.map((warning, index) => (
              <li key={index}>{warning.replaceAll('_', ' ')}</li>
            ))}
          </ul>
          <form
            onSubmit={(event) => {
              event.preventDefault()
              const fields = new FormData(event.currentTarget)
              void action.run(async () =>
                setRecommendations(
                  await getSupplierRecommendations(
                    productId,
                    report.id,
                    choice(fieldValue(fields, 'supplier-mode'), [
                      'savings',
                      'quality',
                      'balanced',
                    ] as const),
                    choice(fieldValue(fields, 'supplier-objective'), [
                      'purchase_outlay',
                      'usable_unit',
                    ] as const),
                    readOptionalPreferences(fields, 'supplier-preference'),
                  ),
                ),
              )
            }}
            onChange={() => setRecommendations(null)}
          >
            <OptionalPreferences
              prefix="supplier-preference"
              onEdit={() => setRecommendations(null)}
            />
            <div className="calculator-grid">
              <label className="calculator-field">
                Review priority
                <select name="supplier-mode">
                  <option value="balanced">Balanced</option>
                  <option value="savings">Savings</option>
                  <option value="quality">Quality</option>
                </select>
              </label>
              <label className="calculator-field">
                Cost objective
                <select name="supplier-objective">
                  <option value="purchase_outlay">Purchase outlay</option>
                  <option value="usable_unit">Cost per usable unit</option>
                </select>
              </label>
            </div>
            <p>
              Only explicitly entered preferences are considered. Mandatory
              exclusions apply in every mode.
            </p>
            <button className="calculator-secondary" disabled={action.busy}>
              Review eligible options
            </button>
          </form>
        </section>
      )}
      {recommendations && (
        <section className="calculator-notice">
          <h3>Options for input review</h3>
          {recommendations.rows.map((row, index) => (
            <article key={index}>
              <p>
                {row.supplier_name}:{' '}
                {row.eligible ? row.reason.replaceAll('_', ' ') : 'Excluded'} ·{' '}
                {row.objective_cost === null
                  ? 'Cost unknown'
                  : usd(row.objective_cost)}{' '}
                · {row.exclusions.join(', ').replaceAll('_', ' ')}
              </p>
              <ul>
                {row.preference_checks.map((check, checkIndex) => (
                  <li key={checkIndex}>
                    {check.label}: {check.status} · {check.message}
                  </li>
                ))}
              </ul>
            </article>
          ))}
          <ul>
            {recommendations.notices.map((notice, index) => (
              <li key={index}>{notice}</li>
            ))}
          </ul>
          <p>
            No recipe substitution or finished-product quality change is
            authorized by this report.
          </p>
        </section>
      )}
      <button
        className="calculator-secondary"
        disabled={action.busy}
        onClick={() => {
          setReport(null)
          setRecommendations(null)
          resource.reload()
        }}
      >
        Reload current input and sources
      </button>
    </>
  )
}
