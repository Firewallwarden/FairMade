import { useCallback, useState } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { ErrorNotice, SignInPrompt } from '../components/Feedback'
import { Field } from '../components/FormFields'
import { PlanPurchaseReview } from '../components/PlanPurchaseReview'
import { useSession } from '../services/session'
import { useResource } from '../hooks/useResource'
import { useAction } from '../hooks/useAction'
import {
  getPublicStorefront,
  getStorefrontListings,
} from '../services/presentation'
import { optimizeBasket, suggestBundles } from '../services/planning'
import { createConversation } from '../services/assistants'
import type {
  BasketRequest,
  BundleRequest,
} from '../services/planning-contract'
import type { CatalogCard } from '../services/catalog-contract'
import type { CartRequest } from '../services/order-contract'
import { buildBasketRequest } from '../utils/shopping-plan'
import { fieldValue } from '../utils/form'
import { usd } from '../utils/presentation'

type Need = {
  id: string
  label: string
  quantity: string
  alternatives: CatalogCard[]
}
type Result =
  | {
      kind: 'basket'
      request: BasketRequest
      data: Awaited<ReturnType<typeof optimizeBasket>>
    }
  | {
      kind: 'bundles'
      request: BundleRequest
      data: Awaited<ReturnType<typeof suggestBundles>>
    }
export function ShoppingPlanPage({
  storefrontId,
  seller = false,
}: {
  storefrontId?: string
  seller?: boolean
}) {
  const session = useSession()
  return (
    <WorkspaceLayout
      title="A little planning. A better-fitting basket."
      intro="Choose acceptable alternatives and a budget. Plans and pair suggestions are not purchases or stock reservations."
    >
      {!storefrontId ? (
        <section className="workspace-panel">
          <h2>Start with one maker.</h2>
          <p>
            Basket optimization and bundle suggestions use one approved
            storefront at a time. Choose a maker, then open “Plan a basket”.
          </p>
          <a className="button-primary" href="#/storefronts">
            Find a maker
          </a>
        </section>
      ) : !session ? (
        <SignInPrompt />
      ) : seller && !session.account.roles.includes('seller') ? (
        <p>Seller access is required for the seller bundle view.</p>
      ) : (
        <PlanWorkspace storefrontId={storefrontId} seller={seller} />
      )}
    </WorkspaceLayout>
  )
}
function PlanWorkspace({
  storefrontId,
  seller,
}: {
  storefrontId: string
  seller: boolean
}) {
  const session = useSession()
  const [offset, setOffset] = useState(0)
  const resource = useResource(
    useCallback(
      async (signal) => {
        const [storefront, listings] = await Promise.all([
          getPublicStorefront(storefrontId, signal),
          getStorefrontListings(storefrontId, offset, signal),
        ])
        return { storefront, listings }
      },
      [storefrontId, offset],
    ),
  )
  const [mode, setMode] = useState<'basket' | 'buyer-bundle' | 'seller-bundle'>(
    seller ? 'seller-bundle' : 'basket',
  )
  const [needs, setNeeds] = useState<Need[]>([
    {
      id: crypto.randomUUID().slice(0, 8),
      label: 'Shopping need 1',
      quantity: '1',
      alternatives: [],
    },
  ])
  const [candidates, setCandidates] = useState<CatalogCard[]>([])
  const [result, setResult] = useState<Result | null>(null)
  const [purchase, setPurchase] = useState<CartRequest | null>(null)
  const [locked, setLocked] = useState(false)
  const action = useAction()
  function invalidate() {
    setResult(null)
    setPurchase(null)
  }
  function updateNeed(id: string, patch: Partial<Need>) {
    setNeeds(
      needs.map((need) => (need.id === id ? { ...need, ...patch } : need)),
    )
    invalidate()
  }
  const names = new Map(
    [...needs.flatMap((need) => need.alternatives), ...candidates].map(
      (card) => [card.id, card.payload.product.title],
    ),
  )
  return (
    <>
      <a href={`#/storefront/${storefrontId}`}>← Maker’s public storefront</a>
      <ErrorNotice error={resource.error || action.error} />
      {resource.loading && (
        <p role="status">Loading approved maker listings…</p>
      )}
      <section className="workspace-panel">
        <h2>
          {resource.data?.storefront.payload.display_name ?? 'Choose your plan'}
        </h2>
        <p>
          These are temporary plans on this page. Reloading clears the
          selections. Prices, eligibility, budget totals and stock checks come
          from the backend; selecting an alternative does not establish
          equivalent quality.
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            const fields = new FormData(event.currentTarget),
              budget = fieldValue(fields, 'plan-budget') || null
            void action.run(async () => {
              invalidate()
              if (mode === 'basket') {
                const request = buildBasketRequest(
                  storefrontId,
                  budget,
                  needs.map((need) => ({
                    group_id: need.id,
                    quantity: Number(need.quantity),
                    alternatives: need.alternatives.map((card) => ({
                      listing_id: card.id,
                      expected_listing_revision: card.published_revision,
                    })),
                  })),
                )
                setResult({
                  kind: 'basket',
                  request,
                  data: await optimizeBasket(request),
                })
              } else {
                if (candidates.length < 2 || candidates.length > 8)
                  throw new Error(
                    'Choose two to eight candidate products for pair suggestions.',
                  )
                const request: BundleRequest = {
                  storefront_id: storefrontId,
                  budget,
                  candidates: candidates.map((card) => ({
                    listing_id: card.id,
                    expected_listing_revision: card.published_revision,
                  })),
                  limit: 3,
                }
                setResult({
                  kind: 'bundles',
                  request,
                  data: await suggestBundles(request, mode === 'seller-bundle'),
                })
              }
            })
          }}
        >
          <fieldset
            className="calculator-form"
            disabled={action.busy || locked}
          >
            <legend className="sr-only">Shopping plan inputs</legend>
            <div className="calculator-grid">
              <label className="calculator-field">
                Plan type
                <select
                  value={mode}
                  onChange={(event) => {
                    const value = event.target.value
                    if (
                      value === 'basket' ||
                      value === 'buyer-bundle' ||
                      value === 'seller-bundle'
                    ) {
                      setMode(value)
                      invalidate()
                    }
                  }}
                >
                  <option value="basket">Buyer basket with alternatives</option>
                  <option value="buyer-bundle">Buyer pair suggestions</option>
                  {session?.account.roles.includes('seller') && (
                    <option value="seller-bundle">
                      Seller pair suggestions (your own storefront only)
                    </option>
                  )}
                </select>
              </label>
              <Field
                name="plan-budget"
                title="Total merchandise budget USD (optional)"
                type="number"
                min="0"
                max="1000000000"
                step="0.01"
                onChange={invalidate}
              />
            </div>
            {mode === 'basket' ? (
              <>
                {needs.map((need, index) => (
                  <section className="workspace-panel" key={need.id}>
                    <h3>{need.label}</h3>
                    <div className="calculator-grid">
                      <label className="calculator-field">
                        Need label
                        <input
                          value={need.label}
                          maxLength={80}
                          required
                          onChange={(event) =>
                            updateNeed(need.id, { label: event.target.value })
                          }
                        />
                      </label>
                      <label className="calculator-field">
                        Quantity of selling units
                        <input
                          type="number"
                          min="1"
                          max="10000"
                          step="1"
                          required
                          value={need.quantity}
                          onChange={(event) =>
                            updateNeed(need.id, {
                              quantity: event.target.value,
                            })
                          }
                        />
                      </label>
                    </div>
                    <p>
                      Choose 1–4 acceptable alternatives for this need.{' '}
                      {need.alternatives.length} selected.
                    </p>
                    <p className="workspace-muted">
                      Alternatives must have the same product type, selling unit
                      and declared contents. Put different goods in separate
                      shopping needs. The backend checks the selling basis; your
                      choice is not a quality-equivalence claim.
                    </p>
                    {need.alternatives
                      .filter(
                        (card) =>
                          !resource.data?.listings.items.some(
                            (item) => item.id === card.id,
                          ),
                      )
                      .map((card) => (
                        <label className="workspace-check" key={card.id}>
                          <input
                            type="checkbox"
                            checked
                            onChange={() =>
                              updateNeed(need.id, {
                                alternatives: need.alternatives.filter(
                                  (item) => item.id !== card.id,
                                ),
                              })
                            }
                          />
                          {card.payload.product.title} · selected from another
                          page
                        </label>
                      ))}
                    {resource.data?.listings.items.map((card) => (
                      <label className="workspace-check" key={card.id}>
                        <input
                          type="checkbox"
                          checked={need.alternatives.some(
                            (item) => item.id === card.id,
                          )}
                          disabled={
                            !need.alternatives.some(
                              (item) => item.id === card.id,
                            ) && need.alternatives.length >= 4
                          }
                          onChange={(event) =>
                            updateNeed(need.id, {
                              alternatives: event.target.checked
                                ? [...need.alternatives, card]
                                : need.alternatives.filter(
                                    (item) => item.id !== card.id,
                                  ),
                            })
                          }
                        />
                        {card.payload.product.title} ·{' '}
                        {usd(card.payload.price.amount)} /{' '}
                        {card.payload.product.selling_unit}
                      </label>
                    ))}
                    <button
                      type="button"
                      className="calculator-remove"
                      disabled={needs.length <= 1}
                      onClick={() => {
                        setNeeds(needs.filter((item) => item.id !== need.id))
                        invalidate()
                      }}
                    >
                      Remove need {index + 1}
                    </button>
                  </section>
                ))}
                <button
                  type="button"
                  className="calculator-secondary"
                  disabled={needs.length >= 4}
                  onClick={() => {
                    setNeeds([
                      ...needs,
                      {
                        id: crypto.randomUUID().slice(0, 8),
                        label: `Shopping need ${needs.length + 1}`,
                        quantity: '1',
                        alternatives: [],
                      },
                    ])
                    invalidate()
                  }}
                >
                  Add shopping need
                </button>
              </>
            ) : (
              <>
                <h3>Select pair candidates</h3>
                <p>
                  Choose 2–8 products. Each suggested pair uses one selling unit
                  of each product, at existing prices. No discount or new
                  listing is created.
                </p>
                {candidates
                  .filter(
                    (card) =>
                      !resource.data?.listings.items.some(
                        (item) => item.id === card.id,
                      ),
                  )
                  .map((card) => (
                    <label className="workspace-check" key={card.id}>
                      <input
                        type="checkbox"
                        checked
                        onChange={() => {
                          setCandidates(
                            candidates.filter((item) => item.id !== card.id),
                          )
                          invalidate()
                        }}
                      />
                      {card.payload.product.title} · selected from another page
                    </label>
                  ))}
                {resource.data?.listings.items.map((card) => (
                  <label className="workspace-check" key={card.id}>
                    <input
                      type="checkbox"
                      checked={candidates.some((item) => item.id === card.id)}
                      disabled={
                        !candidates.some((item) => item.id === card.id) &&
                        candidates.length >= 8
                      }
                      onChange={(event) => {
                        setCandidates(
                          event.target.checked
                            ? [...candidates, card]
                            : candidates.filter((item) => item.id !== card.id),
                        )
                        invalidate()
                      }}
                    />
                    {card.payload.product.title} ·{' '}
                    {usd(card.payload.price.amount)}
                  </label>
                ))}
              </>
            )}
            <div className="workspace-actions">
              <button
                type="button"
                className="calculator-secondary"
                disabled={!offset}
                onClick={() => setOffset(Math.max(0, offset - 12))}
              >
                Previous products
              </button>
              <button
                type="button"
                className="calculator-secondary"
                disabled={(resource.data?.listings.items.length ?? 0) < 12}
                onClick={() => setOffset(offset + 12)}
              >
                Next products
              </button>
              <button className="button-primary">Build a read-only plan</button>
            </div>
          </fieldset>
        </form>
      </section>
      {result && (
        <section className="workspace-panel">
          <p className="eyebrow">Planning result · No stock reserved</p>
          {result.kind === 'basket' ? (
            <>
              <h2>Basket status: {result.data.status.replaceAll('_', ' ')}</h2>
              <p>
                Minimum eligible subtotal:{' '}
                {result.data.minimum_subtotal === null
                  ? 'Not established'
                  : usd(result.data.minimum_subtotal.amount)}
                .{' '}
                {result.data.remaining_budget &&
                  `Remaining budget: ${usd(result.data.remaining_budget.amount)}.`}
              </p>
              {result.data.needs.map((need) => (
                <article key={need.group_id}>
                  <h3>
                    {needs.find((item) => item.id === need.group_id)?.label ??
                      'Shopping need'}
                  </h3>
                  <p>
                    {need.quantity} selling unit(s) ·{' '}
                    {need.chosen_listing_id
                      ? (names.get(need.chosen_listing_id) ??
                        'Selected product')
                      : 'No eligible choice'}
                  </p>
                  <ul>
                    {need.candidates.map((candidate) => (
                      <li key={candidate.listing_id}>
                        {names.get(candidate.listing_id) ?? 'Candidate'}:{' '}
                        {candidate.eligible
                          ? 'eligible within this plan'
                          : candidate.exclusions
                              .join(', ')
                              .replaceAll('_', ' ')}
                        {candidate.affinity_reasons.length > 0 &&
                          ` · ${candidate.affinity_reasons.join(', ').replaceAll('_', ' ')}`}
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
              {result.data.status === 'ready' && result.data.cart && (
                <button
                  className="calculator-secondary"
                  disabled={action.busy || locked}
                  onClick={() => setPurchase(result.data.cart)}
                >
                  Review a separate purchase from this basket
                </button>
              )}
            </>
          ) : (
            <>
              <h2>Pair suggestions</h2>
              <p>
                {result.data.eligible_pairs} eligible pair(s);{' '}
                {result.data.budget_excluded_pairs} over-budget pair(s).{' '}
                {result.data.role === 'seller'
                  ? 'Private seller history is limited to your own storefront.'
                  : 'Buyer affinity is not a quality or fairness verdict.'}
              </p>
              {!result.data.suggestions.length && (
                <p>
                  No eligible suggestions from these candidates. Change your
                  choices or budget.
                </p>
              )}
              {result.data.suggestions.map((suggestion, index) => (
                <article
                  className="workspace-panel"
                  key={suggestion.listings.map((item) => item.id).join('-')}
                >
                  <h3>
                    Pair {index + 1} · {usd(suggestion.subtotal.amount)}
                  </h3>
                  <ul>
                    {suggestion.listings.map((listing) => (
                      <li key={listing.id}>
                        <a href={`#/market/${listing.id}`}>
                          {listing.payload.product.title}
                        </a>{' '}
                        · 1 selling unit
                      </li>
                    ))}
                  </ul>
                  <ul>
                    {suggestion.reasons.map((reason, index) => (
                      <li key={index}>{reason.replaceAll('_', ' ')}</li>
                    ))}
                  </ul>
                  <p>
                    Observed same-order count:{' '}
                    {suggestion.observed_copurchase_orders ?? 'Not disclosed'}.
                  </p>
                  {result.data.role === 'buyer' && suggestion.cart && (
                    <button
                      className="calculator-secondary"
                      disabled={locked || action.busy}
                      onClick={() => setPurchase(suggestion.cart)}
                    >
                      Review a separate purchase of this pair
                    </button>
                  )}
                </article>
              ))}
              <details>
                <summary>Candidate eligibility and exclusions</summary>
                <ul>
                  {result.data.candidates.map((candidate) => (
                    <li key={candidate.listing_id}>
                      {names.get(candidate.listing_id) ?? 'Candidate'}:{' '}
                      {candidate.eligible
                        ? 'eligible'
                        : candidate.exclusions.join(', ').replaceAll('_', ' ')}
                    </li>
                  ))}
                </ul>
              </details>
            </>
          )}
          <ul>
            {result.data.notices.map((notice, index) => (
              <li key={index}>{notice}</li>
            ))}
          </ul>
          {(result.kind === 'basket' || result.data.role === 'buyer') && (
            <button
              className="calculator-secondary"
              disabled={action.busy || locked}
              onClick={() =>
                action.run(async () => {
                  const scope =
                    result.kind === 'basket'
                      ? { role: 'buyer' as const, basket: result.request }
                      : { role: 'buyer' as const, bundles: result.request }
                  const conversation = await createConversation(
                    scope,
                    crypto.randomUUID(),
                  )
                  window.location.hash = `/assistant/conversations/${conversation.id}`
                })
              }
            >
              Ask FairMade about this plan
            </button>
          )}
        </section>
      )}
      {purchase && (
        <PlanPurchaseReview
          key={JSON.stringify(purchase)}
          cart={purchase}
          locked={locked}
          onLock={setLocked}
        />
      )}
    </>
  )
}
