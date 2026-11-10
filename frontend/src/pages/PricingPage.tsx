import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Brand } from '../components/Brand'
import { analyzePricing } from '../services/pricing'
import { percentToRate } from '../services/pricing-contract'
import { ApiError } from '../services/http'
import { costCategories } from '../types/pricing'
import type { PricingResponse } from '../types/pricing'
import type { PricingRequest } from '../types/pricing'
import { PricingResults } from '../components/PricingResults'
import './pricing.css'

function label(value: string) {
  return value
    .replaceAll('_', ' ')
    .replace(/^./, (letter) => letter.toUpperCase())
}

function AmountField({
  name,
  title,
  optional = false,
  max = '1000000000',
  step = '0.000001',
  initial,
}: {
  name: string
  title: string
  optional?: boolean
  max?: string
  step?: string
  initial?: string
}) {
  return (
    <label className="calculator-field" htmlFor={name}>
      {title}
      <input
        id={name}
        name={name}
        type="number"
        min="0"
        max={max}
        step={step}
        required={!optional}
        defaultValue={initial}
        inputMode="decimal"
      />
    </label>
  )
}

export function PricingPage({
  product,
  onAnalyze = analyzePricing,
}: {
  product?: { selling_unit: string }
  onAnalyze?: (
    input: PricingRequest,
    signal?: AbortSignal,
  ) => Promise<PricingResponse>
}) {
  const embedded = Boolean(product)
  const Container = embedded ? 'section' : 'main'
  const Title = embedded ? 'h2' : 'h1'
  const [costRows, setCostRows] = useState([crypto.randomUUID()])
  const [laborRows, setLaborRows] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [result, setResult] = useState<PricingResponse | null>(null)
  const [unit, setUnit] = useState('selling unit')
  const request = useRef<AbortController | null>(null)
  const feedback = useRef<HTMLDivElement>(null)

  useEffect(() => () => request.current?.abort(), [])
  useEffect(() => {
    if (result || error) feedback.current?.focus()
  }, [result, error])

  function clearResult() {
    setResult(null)
    setError(null)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    const form = new FormData(event.currentTarget)
    const value = (key: string) => String(form.get(key) ?? '').trim()
    clearResult()
    try {
      const minimum = percentToRate(value('margin-minimum'))
      const maximum = percentToRate(value('margin-maximum'))
      const feeRate = percentToRate(value('fee-rate'))
      if (Number(minimum) > Number(maximum))
        throw new Error(
          'Your maximum target margin must be at least your minimum.',
        )
      if (Number(maximum) + Number(feeRate) >= 1)
        throw new Error(
          'Processing fees and your maximum target margin together must be less than 100%.',
        )
      setUnit(value('selling-unit'))
      setBusy(true)
      const controller = new AbortController()
      request.current = controller
      const response = await onAnalyze(
        {
          currency: 'USD',
          sellable_units: Number(value('yield')),
          costs: costRows.map((id) => ({
            label: value(`cost-label-${id}`),
            category:
              costCategories.find(
                (category) => category === value(`cost-category-${id}`),
              ) ?? 'other',
            amount: value(`cost-amount-${id}`),
          })),
          labor: laborRows.map((id) => ({
            label: value(`labor-label-${id}`),
            hours: value(`labor-hours-${id}`),
            hourly_rate: value(`labor-rate-${id}`),
          })),
          payment_fees: {
            rate: feeRate,
            fixed_per_order: value('fee-fixed'),
            units_per_order: Number(value('units-per-order')),
          },
          target_margin: { minimum, maximum },
          proposed_prices: value('proposed-price')
            ? [value('proposed-price')]
            : [],
        },
        controller.signal,
      )
      if (!controller.signal.aborted) setResult(response)
    } catch (caught) {
      if (!(caught instanceof Error && caught.name === 'AbortError'))
        setError(
          caught instanceof Error
            ? caught
            : new Error('Unable to calculate. Please try again.'),
        )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="calculator-shell">
      {!embedded && (
        <a
          className="skip-link"
          href="#calculator-main"
          onClick={(event) => {
            event.preventDefault()
            document.getElementById('calculator-main')?.focus()
          }}
        >
          Skip to calculator
        </a>
      )}
      {!embedded && (
        <header className="site-header page-width">
          <Brand />
          <nav className="calculator-nav" aria-label="Main navigation">
            <a href="#home">Home</a>
            <a href="#/pricing" aria-current="page">
              Cost calculator
            </a>
          </nav>
        </header>
      )}
      <Container
        id="calculator-main"
        tabIndex={-1}
        className={
          embedded ? 'embedded-calculator' : 'page-width calculator-main'
        }
      >
        <div className="calculator-intro">
          <p className="eyebrow">For the hands that make it</p>
          <Title>
            Make room for <em>your work.</em>
          </Title>
          <p>
            Understand the costs behind a loaf, a dozen eggs, or whatever you
            make. Start with one batch and let FairMade calculate a price range
            for your targets.
          </p>
        </div>
        <aside className="calculator-notice">
          {embedded
            ? 'Calculating saves a private analysis for this product. It does not publish your costs or a listing.'
            : 'This calculator does not save a product or publish a listing.'}{' '}
          Results use your unverified inputs and deterministic backend
          calculations; they do not establish objective fairness.
        </aside>
        <form onSubmit={submit} onChange={clearResult} aria-busy={busy}>
          <fieldset disabled={busy} className="calculator-form">
            <legend className="sr-only">Production cost calculator</legend>
            <section
              className="calculator-panel"
              aria-labelledby="batch-heading"
            >
              <p className="eyebrow">01 · Your batch</p>
              <h2 id="batch-heading">What are you making?</h2>
              <p>
                All costs below are for the entire batch. Yield means usable
                units after waste. For eggs sold by the dozen, enter the number
                of dozens.
              </p>
              <div className="calculator-grid">
                <label className="calculator-field" htmlFor="selling-unit">
                  One selling unit
                  <input
                    id="selling-unit"
                    name="selling-unit"
                    required
                    maxLength={200}
                    pattern=".*\S.*"
                    defaultValue={product?.selling_unit}
                    readOnly={embedded}
                    placeholder="e.g. one loaf or one dozen eggs"
                  />
                </label>
                <label className="calculator-field" htmlFor="yield">
                  Sellable units in this batch
                  <input
                    id="yield"
                    name="yield"
                    type="number"
                    required
                    min="1"
                    max="1000000"
                    step="1"
                    inputMode="numeric"
                  />
                </label>
              </div>
            </section>
            <section
              className="calculator-panel"
              aria-labelledby="cost-heading"
            >
              <p className="eyebrow">02 · Materials & overhead</p>
              <h2 id="cost-heading">Every little input counts.</h2>
              <p>
                Include ingredients or feed, packaging, and this batch’s share
                of equipment, utilities, and other overhead. Enter USD amounts;
                enter zero only when that cost is known to be zero.
              </p>
              {costRows.map((id, index) => (
                <fieldset className="calculator-row" key={id}>
                  <legend>Cost {index + 1}</legend>
                  <label
                    className="calculator-field"
                    htmlFor={`cost-label-${id}`}
                  >
                    Description
                    <input
                      id={`cost-label-${id}`}
                      name={`cost-label-${id}`}
                      required
                      maxLength={200}
                      pattern=".*\S.*"
                    />
                  </label>
                  <label
                    className="calculator-field"
                    htmlFor={`cost-category-${id}`}
                  >
                    Category
                    <select
                      id={`cost-category-${id}`}
                      name={`cost-category-${id}`}
                    >
                      {costCategories.map((category) => (
                        <option value={category} key={category}>
                          {label(category)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <AmountField
                    name={`cost-amount-${id}`}
                    title="Batch cost (USD)"
                  />
                  <button
                    className="calculator-remove"
                    type="button"
                    aria-label={`Remove cost ${index + 1}`}
                    onClick={() => {
                      setCostRows(costRows.filter((row) => row !== id))
                      clearResult()
                    }}
                  >
                    Remove
                  </button>
                </fieldset>
              ))}
              {!costRows.length && (
                <p>
                  No materials or overhead included. Add any costs needed to
                  avoid understating production costs.
                </p>
              )}
              <button
                className="calculator-secondary"
                type="button"
                disabled={costRows.length >= 200}
                onClick={() => {
                  setCostRows([...costRows, crypto.randomUUID()])
                  clearResult()
                }}
              >
                + Add a cost
              </button>
            </section>
            <section
              className="calculator-panel"
              aria-labelledby="labor-heading"
            >
              <p className="eyebrow">03 · Your time</p>
              <h2 id="labor-heading">Your labor belongs here, too.</h2>
              <p>
                Enter time for the whole batch and your chosen hourly pay. Labor
                is a production cost; profit is calculated separately.
              </p>
              {laborRows.map((id, index) => (
                <fieldset className="calculator-row" key={id}>
                  <legend>Labor {index + 1}</legend>
                  <label
                    className="calculator-field"
                    htmlFor={`labor-label-${id}`}
                  >
                    Task
                    <input
                      id={`labor-label-${id}`}
                      name={`labor-label-${id}`}
                      required
                      maxLength={200}
                      pattern=".*\S.*"
                    />
                  </label>
                  <AmountField
                    name={`labor-hours-${id}`}
                    title="Hours per batch"
                  />
                  <AmountField
                    name={`labor-rate-${id}`}
                    title="Hourly pay (USD)"
                  />
                  <button
                    className="calculator-remove"
                    type="button"
                    aria-label={`Remove labor ${index + 1}`}
                    onClick={() => {
                      setLaborRows(laborRows.filter((row) => row !== id))
                      clearResult()
                    }}
                  >
                    Remove
                  </button>
                </fieldset>
              ))}
              {!laborRows.length && (
                <p>
                  No labor included yet. Add your time to account for the work
                  behind your product.
                </p>
              )}
              <button
                className="calculator-secondary"
                type="button"
                disabled={laborRows.length >= 100}
                onClick={() => {
                  setLaborRows([...laborRows, crypto.randomUUID()])
                  clearResult()
                }}
              >
                + Add labor
              </button>
            </section>
            <section
              className="calculator-panel"
              aria-labelledby="targets-heading"
            >
              <p className="eyebrow">04 · Your targets</p>
              <h2 id="targets-heading">Choose what you’re working toward.</h2>
              <p>
                Margin is profit as a share of selling price, after modeled
                processing fees. These are your targets, not market evidence.
                Enter the fees you expect; FairMade does not supply a PayPal fee
                schedule.
              </p>
              <div className="calculator-grid">
                <AmountField
                  name="margin-minimum"
                  title="Minimum target margin (%)"
                  max="99.9999"
                  step="0.0001"
                />
                <AmountField
                  name="margin-maximum"
                  title="Maximum target margin (%)"
                  max="99.9999"
                  step="0.0001"
                />
                <AmountField
                  name="fee-rate"
                  title="Processing fee (%)"
                  max="99.9999"
                  step="0.0001"
                />
                <AmountField
                  name="fee-fixed"
                  title="Fixed fee per order (USD)"
                />
                <label className="calculator-field" htmlFor="units-per-order">
                  Units sharing one fixed fee
                  <input
                    id="units-per-order"
                    name="units-per-order"
                    type="number"
                    min="1"
                    max="1000000"
                    step="1"
                    required
                    inputMode="numeric"
                    defaultValue="1"
                  />
                </label>
                <AmountField
                  name="proposed-price"
                  title="Price to explore per unit (USD, optional)"
                  optional
                />
              </div>
            </section>
            <div className="calculator-actions">
              <button type="submit" className="button-primary">
                {busy
                  ? 'Calculating…'
                  : embedded
                    ? 'Calculate & save private analysis'
                    : 'Calculate my price range'}
              </button>
              <span>
                {embedded
                  ? 'USD only · Saved privately'
                  : 'USD only · No product is saved'}
              </span>
            </div>
          </fieldset>
        </form>
        {busy && <p role="status">Calculating with the FairMade API…</p>}
        {(error || result) && (
          <div ref={feedback} tabIndex={-1} className="calculator-feedback">
            {error && (
              <div className="calculator-error" role="alert">
                <h2>Let’s check that.</h2>
                <p>{error.message}</p>
                {error instanceof ApiError && error.issues.length > 0 && (
                  <ul>
                    {error.issues.map((issue, index) => (
                      <li key={index}>
                        {issue.field.replace(/^body\.?/, '')}: {issue.message}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            {result && <PricingResults result={result} unit={unit} />}
          </div>
        )}
      </Container>
      {!embedded && (
        <footer className="page-width calculator-footer">
          Made with care. Results are estimates from your inputs; local demand,
          quality evidence, and actual operating costs still matter.
        </footer>
      )}
    </div>
  )
}
