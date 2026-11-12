import { HistorySelection } from '../../components/HistorySelection'
import { useCallback, useState } from 'react'
import { getAnalyses } from '../../services/seller'
import {
  getCostBasis,
  setCostBasis,
  getInsights,
  getForecast,
  getCostCalendar,
  getPricingReviews,
  getPriceAdvice,
  getSalesSummary,
} from '../../services/seller-reports'
import { useResource } from '../../hooks/useResource'
import { useAction } from '../../hooks/useAction'
import { Field } from '../../components/FormFields'
import { ErrorNotice } from '../../components/Feedback'
import { EvidenceDetails } from '../../components/EvidenceDetails'
import { fieldValue } from '../../utils/form'
import { usd } from '../../utils/presentation'

type Reports =
  | { kind: 'insights'; data: Awaited<ReturnType<typeof getInsights>> }
  | { kind: 'forecast'; data: Awaited<ReturnType<typeof getForecast>> }
  | { kind: 'calendar'; data: Awaited<ReturnType<typeof getCostCalendar>> }
  | { kind: 'advice'; data: Awaited<ReturnType<typeof getPriceAdvice>> }
  | { kind: 'sales'; data: Awaited<ReturnType<typeof getSalesSummary>> }

export function BusinessReportsStep({ productId }: { productId: string }) {
  const resource = useResource(
    useCallback(
      async (signal) => {
        const [analyses, reviews, basis] = await Promise.all([
          getAnalyses(productId, signal),
          getPricingReviews(productId, signal),
          getCostBasis(productId, signal),
        ])
        return { analyses, reviews, basis }
      },
      [productId],
    ),
  )
  const [report, setReport] = useState<Reports | null>(null)
  const [mode, setMode] = useState<
    'insights' | 'forecast' | 'calendar' | 'advice' | 'sales'
  >('insights')
  const [dates] = useState(() => {
    const today = new Date()
    const end = new Date(today)
    end.setUTCDate(end.getUTCDate() + 1)
    const start = new Date(today)
    start.setUTCDate(start.getUTCDate() - 29)
    return {
      start: start.toISOString().slice(0, 10),
      end: end.toISOString().slice(0, 10),
    }
  })
  const action = useAction()
  return (
    <section className="workspace-panel">
      <h2>Make decisions with a clearer picture.</h2>
      <p>
        Read-only reports use selected saved economics and backend-verified
        sandbox sales. They do not change your prices, inventory or recipes.
        Missing evidence remains unknown.
      </p>
      <ErrorNotice error={resource.error || action.error} />
      {resource.loading && <p role="status">Loading report sources…</p>}
      {resource.data && (
        <>
          <details>
            <summary>
              Choose a private cost basis for future order snapshots
            </summary>
            <p>
              This choice applies to new orders only. It does not backfill
              missing historical costs or establish actual earnings.
            </p>
            <form
              onSubmit={(event) => {
                event.preventDefault()
                const selected =
                  fieldValue(
                    new FormData(event.currentTarget),
                    'sales-basis',
                  ) || null
                const revision = resource.data?.basis.revision
                if (revision !== undefined)
                  void action.run(async () => {
                    await setCostBasis(productId, revision, selected)
                    resource.reload()
                  }, 'Private future-order cost basis saved.')
              }}
            >
              <HistorySelection disabled={action.busy} productId={productId} kind="analyses" title="Future-order cost basis" name="sales-basis" initialValue={resource.data.basis.analysis_id ?? ''} />
              <div className="workspace-actions">
                <button
                  type="submit"
                  className="calculator-secondary"
                  disabled={action.busy}
                >
                  Save future-order cost basis
                </button>
              </div>
            </form>
          </details>
          <form
            onSubmit={(event) => {
              event.preventDefault()
              const fields = new FormData(event.currentTarget)
              void action.run(async () => {
                setReport(null)
                if (mode === 'insights')
                  setReport({
                    kind: mode,
                    data: await getInsights(
                      productId,
                      Number(fieldValue(fields, 'insight-days')),
                      fieldValue(fields, 'insight-analysis') || null,
                    ),
                  })
                if (mode === 'forecast')
                  setReport({
                    kind: mode,
                    data: await getForecast(
                      productId,
                      Number(fieldValue(fields, 'forecast-lookback')),
                      Number(fieldValue(fields, 'forecast-horizon')),
                    ),
                  })
                if (mode === 'calendar')
                  setReport({
                    kind: mode,
                    data: await getCostCalendar(
                      productId,
                      Number(fieldValue(fields, 'calendar-months')),
                    ),
                  })
                if (mode === 'advice')
                  setReport({
                    kind: mode,
                    data: await getPriceAdvice(
                      productId,
                      fieldValue(fields, 'advice-review'),
                    ),
                  })
                if (mode === 'sales')
                  setReport({
                    kind: mode,
                    data: await getSalesSummary(
                      fieldValue(fields, 'sales-start'),
                      fieldValue(fields, 'sales-end'),
                    ),
                  })
              })
            }}
            onChange={() => setReport(null)}
          >
            <fieldset disabled={action.busy} className="calculator-form">
              <legend className="sr-only">Choose report</legend>
              <label className="calculator-field">
                Report
                <select
                  value={mode}
                  onChange={(event) => {
                    const value = event.target.value
                    if (
                      value === 'insights' ||
                      value === 'forecast' ||
                      value === 'calendar' ||
                      value === 'advice' ||
                      value === 'sales'
                    )
                      setMode(value)
                  }}
                >
                  <option value="insights">
                    Margin, waste and cost insights
                  </option>
                  <option value="advice">Conditional pricing advice</option>
                  <option value="forecast">
                    Observed-sales baseline & stock planning
                  </option>
                  <option value="calendar">
                    Saved cost calendar & annual comparisons
                  </option>
                  <option value="sales">
                    Seller-wide sandbox sales & estimated profit
                  </option>
                </select>
              </label>
              {mode === 'insights' && (
                <div className="calculator-grid">
                  <Field
                    name="insight-days"
                    title="Period length (days)"
                    type="number"
                    min="1"
                    max="90"
                    step="1"
                    required
                    defaultValue="30"
                  />
                  <HistorySelection disabled={action.busy} productId={productId} kind="analyses" title="Pricing source" name="insight-analysis" />
                </div>
              )}
              {mode === 'advice' && (
                <HistorySelection disabled={action.busy} productId={productId} kind="pricing-reviews" title="Saved pricing review" name="advice-review" required />
              )}
              {mode === 'forecast' && (
                <div className="calculator-grid">
                  <Field
                    name="forecast-lookback"
                    title="Closed historical days"
                    type="number"
                    min="14"
                    max="90"
                    step="1"
                    required
                    defaultValue="28"
                  />
                  <Field
                    name="forecast-horizon"
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
              {mode === 'calendar' && (
                <Field
                  name="calendar-months"
                  title="Closed save-month window"
                  type="number"
                  min="1"
                  max="36"
                  step="1"
                  required
                  defaultValue="24"
                />
              )}
              {mode === 'sales' && (
                <div className="calculator-grid">
                  <Field
                    name="sales-start"
                    title="Capture period starts (UTC date)"
                    type="date"
                    required
                    defaultValue={dates.start}
                  />
                  <Field
                    name="sales-end"
                    title="Exclusive end date (1–366 days later)"
                    type="date"
                    required
                    defaultValue={dates.end}
                  />
                </div>
              )}
              <div className="workspace-actions">
                <button className="button-primary" type="submit">
                  Build backend report
                </button>
              </div>
            </fieldset>
          </form>
        </>
      )}
      {action.notice && <p role="status">{action.notice}</p>}
      {report && <ReportView report={report} />}
      <div className="workspace-actions">
        <button
          className="calculator-secondary"
          disabled={action.busy}
          onClick={resource.reload}
        >
          Reload current report sources
        </button>
      </div>
    </section>
  )
}

function ReportView({ report }: { report: Reports }) {
  if (report.kind === 'sales')
    return (
      <div className="calculator-notice">
        <h3>Sandbox capture-cohort sales</h3>
        <p>
          {report.data.sales_count} captured sale(s) · Gross{' '}
          {usd(report.data.gross_sales)} · Completed refunds{' '}
          {usd(report.data.completed_refunds)}.
        </p>
        <p>
          Estimated profit:{' '}
          {report.data.estimated_profit === null
            ? 'Unavailable — required evidence is missing'
            : usd(report.data.estimated_profit)}
          .
        </p>
        <p>
          Missing fee records: {report.data.missing_fee_count}; missing cost
          snapshots: {report.data.missing_cost_count}; fully covered sales:{' '}
          {report.data.covered_sales_count}.
        </p>
        <p>
          These are modeled costs and shared sandbox merchant fees, not actual
          seller payouts or an earnings statement.
        </p>
        <ul>
          {report.data.warnings.map((item, index) => (
            <li key={index}>{item.replaceAll('_', ' ')}</li>
          ))}
        </ul>
      </div>
    )
  const notices = report.data.notices
  return (
    <div className="calculator-notice" aria-label="Backend business report">
      {report.kind === 'insights' && (
        <>
          <h3>On-demand business insights</h3>
          <p>
            As of {report.data.as_of_date}, per {report.data.selling_unit}.
            Pricing status: {report.data.pricing.status.replaceAll('_', ' ')}.
          </p>
          <dl className="calculator-breakdown">
            {Object.entries(report.data.pricing)
              .filter(([key]) => key !== 'status')
              .map(([key, value]) => (
                <div key={key}>
                  <dt>{key.replaceAll('_', ' ')}</dt>
                  <dd>{value === null ? 'Unknown' : usd(value)}</dd>
                </div>
              ))}
          </dl>
          {!report.data.alerts.length && (
            <p>
              No alerts from the available evidence. This does not establish
              that all costs or risks are known.
            </p>
          )}
          {report.data.alerts.map((alert) => (
            <article key={alert.code}>
              <h4>
                {alert.severity}: {alert.message}
              </h4>
              <p>{alert.suggested_review}</p>
            </article>
          ))}
          <details>
            <summary>Cost, expense, output and waste evidence</summary>
            <EvidenceDetails value={report.data.details} />
          </details>
        </>
      )}
      {report.kind === 'forecast' && (
        <>
          <h3>Observed-sales baseline</h3>
          <p>
            Status: {report.data.status.replaceAll('_', ' ')}. Recorded{' '}
            {report.data.history.units} units on{' '}
            {report.data.history.sale_dates} sale date(s),{' '}
            {report.data.history.start_date} to {report.data.history.end_date}.
          </p>
          <p>
            Daily observed rate: {report.data.daily_rate ?? 'Unknown'};
            conditional projected units:{' '}
            {report.data.projected_units ?? 'Unknown'} (
            {report.data.selling_unit}).
          </p>
          <p>
            This is not validated demand or seasonality. Sparse history is not
            replaced with invented sales.
          </p>
          <details>
            <summary>Inventory projection</summary>
            <EvidenceDetails value={report.data.inventory} />
          </details>
          <ul>
            {report.data.warnings.map((item, index) => (
              <li key={index}>{item.replaceAll('_', ' ')}</li>
            ))}
          </ul>
        </>
      )}
      {report.kind === 'calendar' && (
        <>
          <h3>Saved cost calendar</h3>
          <p>
            {report.data.status.replaceAll('_', ' ')} · Seasonality{' '}
            {report.data.seasonality.replaceAll('_', ' ')}. Save months are not
            purchase dates or actual expenses.
          </p>
          <div className="calculator-table-scroll">
            <table>
              <caption>
                Closed monthly snapshots per {report.data.selling_unit}
              </caption>
              <thead>
                <tr>
                  <th>Month</th>
                  <th>Status</th>
                  <th>Records</th>
                  <th>Unit cost</th>
                </tr>
              </thead>
              <tbody>
                {report.data.months.map((month) => (
                  <tr key={month.month}>
                    <td>{month.month}</td>
                    <td>{month.status.replaceAll('_', ' ')}</td>
                    <td>{month.record_count}</td>
                    <td>
                      {month.unit_cost === null
                        ? 'Unknown'
                        : usd(month.unit_cost)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <details>
            <summary>Descriptive year-over-year changes</summary>
            <EvidenceDetails value={report.data.comparisons} />
          </details>
        </>
      )}
      {report.kind === 'advice' && (
        <>
          <h3>Conditional price review</h3>
          <p>
            Status: {report.data.status.replaceAll('_', ' ')} · Quality:{' '}
            {report.data.quality_status.replaceAll('_', ' ')}.
          </p>
          <p>
            Modeled break-even: {usd(report.data.break_even)}. Seller-target
            range: {usd(report.data.target.minimum)} –{' '}
            {usd(report.data.target.maximum)} per {report.data.selling_unit}.
          </p>
          <p>
            {report.data.recommended
              ? `Conditional range to review: ${usd(report.data.recommended.minimum)} – ${usd(report.data.recommended.maximum)}.`
              : 'No price recommendation is established from this evidence.'}
          </p>
          <ul>
            {report.data.reasons.map((item, index) => (
              <li key={index}>{item.replaceAll('_', ' ')}</li>
            ))}
          </ul>
          <p>
            No price is automatically applied and no objective fairness verdict
            is made.
          </p>
          <details>
            <summary>Selected dated market sources</summary>
            <EvidenceDetails value={report.data.sources} />
          </details>
        </>
      )}
      <ul>
        {notices.map((notice, index) => (
          <li key={index}>{notice}</li>
        ))}
      </ul>
    </div>
  )
}
