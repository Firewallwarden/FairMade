import type { PricingResponse } from '../types/pricing'

const usd = (value: string) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 6 }).format(Number(value))
const percent = (value: string | null) => value === null ? 'Not available' : new Intl.NumberFormat('en-US', { style: 'percent', maximumFractionDigits: 2 }).format(Number(value))

export function PricingResults({ result, unit }: { result: PricingResponse; unit: string }) {
  return <section className="calculator-results" aria-labelledby="results-heading">
    <p className="eyebrow">Your cost picture · Seller-reported inputs</p>
    <h2 id="results-heading">A little more understanding.</h2>
    <p>Backend-calculated estimates per {unit}. This range follows your margin targets and modeled fees; it is not a verified local market price.</p>
    <dl className="calculator-metrics">
      <div><dt>Production cost per unit</dt><dd>{usd(result.costs.unit_cost)}</dd></div>
      <div><dt>Break-even price</dt><dd>{usd(result.break_even_price)}</dd></div>
      <div className="calculator-range"><dt>Price range for your targets</dt><dd>{usd(result.sustainable_price_range.minimum)} – {usd(result.sustainable_price_range.maximum)}</dd></div>
    </dl>
    <details open><summary>What went into the batch</summary><dl className="calculator-breakdown">
      {Object.entries(result.costs.category_totals).map(([category, amount]) => <div key={category}><dt>{category.replaceAll('_', ' ')}</dt><dd>{usd(amount)}</dd></div>)}
      <div><dt>Labor</dt><dd>{usd(result.costs.labor_total)}</dd></div>
      <div><dt>Total production cost</dt><dd>{usd(result.costs.batch_total)}</dd></div>
    </dl><p>Modeled fixed processing fee allocated per unit: {usd(result.fixed_fee_per_unit)}. Processing fees are separate from production costs.</p></details>
    {result.scenarios.length > 0 && <div className="calculator-table-scroll"><table><caption>Your price scenarios</caption><thead><tr><th scope="col">Unit price</th><th scope="col">Fee per unit</th><th scope="col">Profit per unit</th><th scope="col">Batch profit</th><th scope="col">Margin</th><th scope="col">Position</th></tr></thead><tbody>{result.scenarios.map((scenario, index) => <tr key={index}>
      <td>{usd(scenario.price)}</td><td>{usd(scenario.processing_fee_per_unit)}</td><td>{usd(scenario.profit_per_unit)}</td><td>{usd(scenario.batch_profit)}</td><td>{percent(scenario.margin)}</td><td>{scenario.below_break_even ? 'Below break-even' : scenario.below_target_margin ? 'Below minimum target' : 'Meets minimum target'}</td>
    </tr>)}</tbody></table></div>}
    {result.warnings.length > 0 && <aside className="calculator-notice"><h3>Keep in mind</h3><ul>{result.warnings.map((warning, index) => <li key={index}>{warning.message}</li>)}</ul></aside>}
    <details><summary>Assumptions and calculation basis</summary><ul>{result.assumptions.map((assumption, index) => <li key={index}>{assumption}</li>)}</ul><p>Calculation version: {result.calculation_version}. Seller-supplied inputs are unverified. No AI provider or external price lookup is used.</p></details>
  </section>
}
