import type { Passport } from '../services/catalog-contract'
import { ruleDescription, usd } from '../utils/presentation'

export function PassportView({ passport }: { passport: Passport }) {
  return (
    <section
      className="workspace-panel passport-view"
      aria-label="Fair Price Passport"
    >
      <p className="eyebrow">Behind the price · Seller-reported, unverified</p>
      <h2>Fair Price Passport</h2>
      <p>
        <strong>{passport.product.title}</strong> · {usd(passport.price.amount)}{' '}
        per {passport.product.selling_unit}.
      </p>
      <p>{passport.product.description}</p>
      <p>
        This is the seller-approved disclosure, reviewed on{' '}
        {passport.reviewed_on}. It explains what the seller chose to share; it
        does not certify quality or establish that the price is objectively
        fair.
      </p>
      <details>
        <summary>The costs behind it</summary>
        {passport.costs ? (
          <dl className="calculator-breakdown">
            {Object.entries(passport.costs.category_costs_per_unit).map(
              ([category, amount]) => (
                <div key={category}>
                  <dt>{category.replaceAll('_', ' ')}</dt>
                  <dd>{usd(amount)}</dd>
                </div>
              ),
            )}
            {passport.costs.labor_per_unit !== null && (
              <div>
                <dt>Labor per unit</dt>
                <dd>{usd(passport.costs.labor_per_unit)}</dd>
              </div>
            )}
            {passport.costs.unit_cost !== null && (
              <div>
                <dt>Total production cost per unit</dt>
                <dd>{usd(passport.costs.unit_cost)}</dd>
              </div>
            )}
          </dl>
        ) : (
          <p>
            The seller has not disclosed cost categories. Missing figures are
            not zero costs.
          </p>
        )}
        <p>
          Only approved categories are shown. Individual recipes, private
          records and undisclosed costs are not included.
        </p>
      </details>
      <details>
        <summary>Quality and evidence</summary>
        {passport.quality_requirements?.length ? (
          <ul>
            {passport.quality_requirements.map((rule) => (
              <li key={rule.key}>
                <strong>{rule.label}:</strong> {ruleDescription(rule)}
              </li>
            ))}
          </ul>
        ) : (
          <p>No quality requirements have been disclosed.</p>
        )}
        {passport.quality_summary && (
          <p>
            Claim-check summary:{' '}
            {passport.quality_summary.status.replaceAll('_', ' ')}. Evaluations:{' '}
            {passport.quality_summary.evaluation_count}; failed:{' '}
            {passport.quality_summary.failed_count}; unknown or unevaluated:{' '}
            {passport.quality_summary.unknown_or_unevaluated_count}; outdated:{' '}
            {passport.quality_summary.outdated_count}.
          </p>
        )}
        <p>
          Seller requirements and reported claim matches are not independent
          certifications.
        </p>
      </details>
      <details>
        <summary>Local price context</summary>
        {passport.market_context ? (
          <>
            <p>
              Status: {passport.market_context.status.replaceAll('_', ' ')}.
              Included observations: {passport.market_context.included_count}.
            </p>
            {passport.market_context.quantity && (
              <p>
                Comparison basis: {passport.market_context.quantity.value}{' '}
                {passport.market_context.quantity.unit}, declared by the seller.
              </p>
            )}
            {passport.market_context.minimum !== null &&
              passport.market_context.maximum !== null && (
                <p>
                  Disclosed comparison range:{' '}
                  {usd(passport.market_context.minimum)} –{' '}
                  {usd(passport.market_context.maximum)} on that comparison
                  basis.
                </p>
              )}
          </>
        ) : (
          <p>
            No local comparison context has been disclosed. FairMade has not
            independently searched local stores for this product.
          </p>
        )}
      </details>
      <details>
        <summary>Sources and limitations</summary>
        <ul>
          {passport.notices.map((notice, index) => (
            <li key={index}>{notice}</li>
          ))}
        </ul>
        <p>
          This Passport contains approved saved evidence. Ask FairMade offers a
          separate local AI explanation; it does not independently verify claims
          or retrieve live prices.
        </p>
      </details>
    </section>
  )
}
