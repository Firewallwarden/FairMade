import { HistorySelection } from './HistorySelection'
import { useCallback, useState } from 'react'
import { getPricingReviews } from '../services/seller-reports'
import { getSourcingInputs, getSupplierReports } from '../services/suppliers'
import { useResource } from '../hooks/useResource'
import { ErrorNotice } from './Feedback'
import { Field } from './FormFields'
import { EvidenceDetails } from './EvidenceDetails'
import { OptionalPreferences } from './OptionalPreferences'

export function SelectedConversationContext({
  scope,
}: {
  scope: Record<string, unknown>
}) {
  const labels: Record<string, string> = {
    analysis_id: 'Saved production analysis',
    pricing_review_id: 'Saved pricing review and conditional price advice',
    supplier_report_id: 'Saved supplier comparison',
    history_period: 'Private sandbox sales history',
    insights: 'Margin, cost and waste insights',
    forecast: 'Observed-sales baseline',
    cost_calendar: 'Saved-cost calendar',
    recommendations: 'Supplier recommendations',
    bundles: 'Bundle planning',
  }
  const selected = Object.entries(labels).filter(([key]) => scope[key] != null)
  return (
    <details className="workspace-panel">
      <summary>Sources selected for this conversation</summary>
      {scope.role === 'buyer' ? (
        <>
          <p>
            {scope.basket
              ? 'Selected basket planning context and approved public listing disclosures.'
              : scope.bundles
                ? 'Selected pair-planning context and approved public listing disclosures.'
                : `Approved public disclosures from ${Array.isArray(scope.listing_ids) ? scope.listing_ids.length : 0} selected listing(s).`}{' '}
            Private seller inputs are excluded. Plans do not reserve stock.
          </p>
          <p>
            Your own buyer preferences may also apply if you explicitly enabled
            personalization. <a href="#/preferences">Manage that choice.</a>
          </p>
        </>
      ) : (
        <>
          <p>
            Private product economics and current mandatory Quality Locks.
            Recipe inputs:{' '}
            {scope.include_recipe_inputs === true
              ? 'explicitly included'
              : 'not included'}
            .
          </p>
          <ul>
            {selected.map(([key, label]) => (
              <li key={key}>
                {label}
                {typeof scope[key] === 'object' && (
                  <EvidenceDetails value={scope[key]} />
                )}
              </li>
            ))}
          </ul>
          <p>
            A pricing review selects its own cost analysis. Sources are
            rechecked when history is opened; an old answer may be withheld if
            the evidence changes.
          </p>
        </>
      )}
    </details>
  )
}

export function SellerAssistantContext({ productId }: { productId: string }) {
  const sources = useResource(
    useCallback(
      async (signal) => {
        const [reviews, inputs] = await Promise.all([
          getPricingReviews(productId, signal),
          getSourcingInputs(productId, signal),
        ])
        return { reviews, inputs }
      },
      [productId],
    ),
  )
  const [input, setInput] = useState('')
  const [report, setReport] = useState('')
  const reports = useResource(
    useCallback(
      (signal) =>
        input
          ? getSupplierReports(productId, input, signal)
          : Promise.resolve(null),
      [productId, input],
    ),
  )
  const [history, setHistory] = useState(false)
  const [insights, setInsights] = useState(false)
  const [forecast, setForecast] = useState(false)
  const [calendar, setCalendar] = useState(false)
  const [recommendations, setRecommendations] = useState(false)
  const [dates] = useState(() => {
    const end = new Date()
    end.setUTCDate(end.getUTCDate() + 1)
    const start = new Date()
    start.setUTCDate(start.getUTCDate() - 29)
    return {
      start: start.toISOString().slice(0, 10),
      end: end.toISOString().slice(0, 10),
    }
  })
  return (
    <details>
      <summary>Choose more private business context</summary>
      <p>
        Include only the sources you want to discuss. Report periods are
        recalculated against current accessible evidence when you ask or reopen
        history. These are private explanations, not permission to change
        prices, recipes or stock.
      </p>
      <p>
        A pricing review uses its selected cost analysis. Leave the pricing
        source on the automatic selection, or choose the same analysis used by
        that review.
      </p>
      <ErrorNotice error={sources.error || reports.error} />
      {sources.loading && <p role="status">Loading saved review sources…</p>}
      {sources.data && (
        <div className="calculator-grid">
          <HistorySelection productId={productId} kind="pricing-reviews" title="Saved pricing review" name="assistant-review" />
          <HistorySelection productId={productId} kind="sourcing-inputs" title="Ingredient/material supplier context" value={input} onSelect={(id) => {
                setInput(id)
                setReport('')
                setRecommendations(false)
              }} />
        </div>
      )}
      {input && reports.loading && (
        <p role="status">Loading saved supplier reports…</p>
      )}
      {reports.data && (
        <HistorySelection productId={productId} kind="supplier-comparisons" title="Saved supplier report" key={input} inputId={input} name="assistant-supplier-report" value={report} onSelect={(id) => {
              setReport(id)
              if (!id) setRecommendations(false)
            }} />
      )}
      {report && (
        <>
          <label className="workspace-check">
            <input
              type="checkbox"
              name="assistant-recommendations"
              checked={recommendations}
              onChange={(event) => setRecommendations(event.target.checked)}
            />
            Include supplier recommendation context.
          </label>
          {recommendations && (
            <div className="calculator-grid">
              <OptionalPreferences prefix="assistant-preference" />
              <label className="calculator-field">
                Review priority
                <select name="assistant-priority">
                  <option value="balanced">Balanced</option>
                  <option value="savings">Savings</option>
                  <option value="quality">Quality</option>
                </select>
              </label>
              <label className="calculator-field">
                Cost objective
                <select name="assistant-objective">
                  <option value="purchase_outlay">Total purchase outlay</option>
                  <option value="usable_unit">Cost per usable unit</option>
                </select>
              </label>
              <p>
                Only entered preferences apply. Mandatory Quality Lock
                exclusions apply in every mode.
              </p>
            </div>
          )}
        </>
      )}
      <label className="workspace-check">
        <input
          type="checkbox"
          name="assistant-history"
          checked={history}
          onChange={(event) => setHistory(event.target.checked)}
        />
        Include private sandbox sales/profit history.
      </label>
      {history && (
        <div className="calculator-grid">
          <Field
            name="assistant-history-start"
            title="History starts (UTC)"
            type="date"
            required
            defaultValue={dates.start}
          />
          <Field
            name="assistant-history-end"
            title="Exclusive history end (1–366 days later)"
            type="date"
            required
            defaultValue={dates.end}
          />
        </div>
      )}
      <label className="workspace-check">
        <input
          type="checkbox"
          name="assistant-insights"
          checked={insights}
          onChange={(event) => setInsights(event.target.checked)}
        />
        Include margin, cost and waste insights.
      </label>
      {insights && (
        <Field
          name="assistant-insight-days"
          title="Insight period (days)"
          type="number"
          min="1"
          max="90"
          step="1"
          required
          defaultValue="30"
        />
      )}
      <label className="workspace-check">
        <input
          type="checkbox"
          name="assistant-forecast"
          checked={forecast}
          onChange={(event) => setForecast(event.target.checked)}
        />
        Include an observed-sales baseline and inventory projection.
      </label>
      {forecast && (
        <div className="calculator-grid">
          <Field
            name="assistant-lookback"
            title="Closed historical days"
            type="number"
            min="14"
            max="90"
            step="1"
            required
            defaultValue="28"
          />
          <Field
            name="assistant-horizon"
            title="Conditional projection horizon (days)"
            type="number"
            min="1"
            max="30"
            step="1"
            required
            defaultValue="7"
          />
        </div>
      )}
      <label className="workspace-check">
        <input
          type="checkbox"
          name="assistant-calendar"
          checked={calendar}
          onChange={(event) => setCalendar(event.target.checked)}
        />
        Include the saved-cost calendar.
      </label>
      {calendar && (
        <Field
          name="assistant-calendar-months"
          title="Closed save-month window"
          type="number"
          min="1"
          max="36"
          step="1"
          required
          defaultValue="24"
        />
      )}
      <p>
        Sales are sandbox captures, saved cost months are not actual purchase
        dates, and sparse forecasts remain unknown. Choosing more context does
        not independently verify the evidence.
      </p>
    </details>
  )
}
