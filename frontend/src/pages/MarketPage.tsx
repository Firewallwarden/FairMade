import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { Field } from '../components/FormFields'
import { ErrorNotice } from '../components/Feedback'
import { LeafSprig } from '../components/LeafSprig'
import { browseMarket } from '../services/commerce'
import { useResource } from '../hooks/useResource'
import { fieldValue } from '../utils/form'
import { usd } from '../utils/presentation'
import { publicMediaUrl } from '../services/media'
import type { CatalogCard } from '../services/catalog-contract'

export function MarketPage() {
  const [filters, setFilters] = useState({
    q: '',
    product_type: '',
    location: '',
    availability: '',
    sort: 'newest',
    reference_unit: '',
  })
  const [sort, setSort] = useState('newest')
  const [selected, setSelected] = useState<CatalogCard[]>([])
  const normalizedSort = sort === 'unit_price' || sort === 'value'
  const [offset, setOffset] = useState(0)
  const resource = useResource(
    useCallback(
      (signal) => browseMarket(filters, offset, signal),
      [filters, offset],
    ),
  )
  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setFilters({
      q: fieldValue(form, 'market-query'),
      product_type: fieldValue(form, 'market-type'),
      location: fieldValue(form, 'market-location'),
      availability: fieldValue(form, 'market-availability'),
      sort,
      reference_unit: normalizedSort
        ? fieldValue(form, 'market-reference-unit')
        : '',
    })
    setOffset(0)
  }

  return (
    <WorkspaceLayout
      title="Good things, close to home."
      intro="Browse seller-approved listings and discover the work behind their prices. Location labels and product claims are seller-reported."
    >
      <section className="workspace-panel">
        <form onSubmit={search}>
          <div className="calculator-grid">
            <Field
              name="market-query"
              title="Search products or makers"
              type="search"
              maxLength={200}
            />
            <Field
              name="market-location"
              title="Location label"
              maxLength={200}
              placeholder="e.g. Exampletown"
            />
            <label className="calculator-field">
              Product type
              <select name="market-type" required={normalizedSort}>
                <option value="">All products</option>
                <option value="sourdough">Sourdough</option>
                <option value="eggs">Eggs</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label className="calculator-field">
              Order results
              <select
                name="market-sort"
                value={sort}
                onChange={(event) => setSort(event.target.value)}
              >
                <option value="newest">Newest listings</option>
                <option value="price_asc">
                  Listed selling-unit price: low to high
                </option>
                <option value="price_desc">
                  Listed selling-unit price: high to low
                </option>
                <option value="quality">
                  Disclosed quality-check evidence
                </option>
                <option value="unit_price">Standard unit price</option>
                <option value="value">
                  Quality evidence, availability & unit price
                </option>
              </select>
            </label>
            {normalizedSort && (
              <label className="calculator-field">
                Compare prices per
                <select name="market-reference-unit" required>
                  <option value="">Choose a reference unit</option>
                  {['kg', 'l', 'egg', 'loaf', 'item'].map((unit) => (
                    <option key={unit}>{unit}</option>
                  ))}
                </select>
              </label>
            )}
            <label className="calculator-field">
              Availability
              <select name="market-availability">
                <option value="">All availability</option>
                <option value="available">Available</option>
                <option value="unavailable">Unavailable</option>
                <option value="unknown">Unknown stock</option>
              </select>
            </label>
          </div>
          <div className="workspace-actions">
            <button className="button-primary" type="submit">
              Find your kind of good
            </button>
          </div>
        </form>
      </section>
      <ErrorNotice error={resource.error} />
      {selected.length > 0 && (
        <section
          className="workspace-panel"
          aria-label="Selected comparison products"
        >
          <h2>Compare what matters to you.</h2>
          <p>
            {selected.length}/4 selected. Different sizes or disclosed claims do
            not establish equivalent quality.
          </p>
          <ul>
            {selected.map((card) => (
              <li key={card.id}>
                {card.payload.product.title}{' '}
                <button
                  className="calculator-remove"
                  onClick={() =>
                    setSelected(selected.filter((item) => item.id !== card.id))
                  }
                >
                  Remove from comparison
                </button>
              </li>
            ))}
          </ul>
          {selected.length >= 2 ? (
            <a
              className="button-primary"
              href={`#/compare/${selected.map((card) => card.id).join(',')}`}
            >
              Compare selected products
            </a>
          ) : (
            <p>Choose at least one more product.</p>
          )}
        </section>
      )}
      {resource.loading && <p role="status">Finding goods at the market…</p>}
      {resource.data && (
        <>
          {!resource.data.items.length && (
            <div className="workspace-empty">
              <h2>A little room to grow.</h2>
              <p>
                No matching listings on this page. Try broader filters or
                publish your first approved product.
              </p>
              <a href="#/seller">Visit the seller workspace</a>
            </div>
          )}
          <div className="workspace-grid">
            {resource.data.items.map((card) => (
              <article className="workspace-panel market-card" key={card.id}>
                <a
                  href={`#/market/${card.id}`}
                  className="market-card-art"
                  tabIndex={-1}
                  aria-hidden="true"
                >
                  {card.payload.photos[0] ? (
                    <img
                      src={publicMediaUrl(card.payload.photos[0].src)}
                      alt=""
                      loading="lazy"
                    />
                  ) : (
                    <>
                      <LeafSprig />
                      <span>
                        {card.payload.product.product_type === 'sourdough'
                          ? 'From the oven'
                          : card.payload.product.product_type === 'eggs'
                            ? 'From the coop'
                            : 'Made with care'}
                      </span>
                    </>
                  )}
                </a>
                <p className="workspace-muted">
                  {card.payload.seller_display_name}
                  {card.payload.location ? ` · ${card.payload.location}` : ''}
                </p>
                <h2>
                  <a href={`#/market/${card.id}`}>
                    {card.payload.product.title}
                  </a>
                </h2>
                <p>{card.payload.summary}</p>
                <p>
                  <strong>{usd(card.payload.price.amount)}</strong> /{' '}
                  {card.payload.product.selling_unit}
                </p>
                <p className="workspace-status">
                  {card.availability.status === 'available'
                    ? `${card.availability.available_units} available`
                    : card.availability.status === 'unavailable'
                      ? 'Currently unavailable'
                      : 'Stock unknown'}
                </p>
                <p className="workspace-muted">
                  Seller-approved Passport · Unverified inputs
                </p>
                {resource.data?.ordering?.items
                  .filter((item) => item.listing_id === card.id)
                  .map((signal) => (
                    <details key={signal.listing_id}>
                      <summary>Why it appears here</summary>
                      <p>
                        {signal.comparison_status === 'not_compared'
                          ? 'Not compared on the selected basis'
                          : 'Ordered under the selected policy'}{' '}
                        · {signal.quality_status.replaceAll('_', ' ')}.
                      </p>
                      <ul>
                        {signal.reasons.map((reason, index) => (
                          <li key={index}>{reason.replaceAll('_', ' ')}</li>
                        ))}
                      </ul>
                    </details>
                  ))}
                <label className="workspace-check">
                  <input
                    type="checkbox"
                    checked={selected.some((item) => item.id === card.id)}
                    disabled={
                      selected.length >= 4 &&
                      !selected.some((item) => item.id === card.id)
                    }
                    onChange={(event) =>
                      setSelected(
                        event.target.checked
                          ? [...selected, card]
                          : selected.filter((item) => item.id !== card.id),
                      )
                    }
                  />
                  Compare {card.payload.product.title}
                </label>
              </article>
            ))}
          </div>
          {resource.data.ordering && (
            <details className="workspace-panel">
              <summary>Ordering basis and limitations</summary>
              <p>
                {resource.data.ordering.compared_count} compared;{' '}
                {resource.data.ordering.not_compared_count} not compared, from{' '}
                {resource.data.ordering.candidate_count} candidates.
              </p>
              <ul>
                {resource.data.ordering.notices.map((notice, index) => (
                  <li key={index}>{notice}</li>
                ))}
              </ul>
            </details>
          )}
          <div className="workspace-actions">
            <button
              className="calculator-secondary"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - 12))}
            >
              Previous
            </button>
            <button
              className="calculator-secondary"
              disabled={resource.data.items.length < 12}
              onClick={() => setOffset(offset + 12)}
            >
              Next
            </button>
          </div>
        </>
      )}
      <button className="calculator-secondary" onClick={resource.reload}>
        Refresh listings
      </button>
    </WorkspaceLayout>
  )
}
