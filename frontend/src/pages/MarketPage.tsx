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

export function MarketPage() {
  const [filters, setFilters] = useState({
    q: '',
    product_type: '',
    location: '',
    availability: '',
  })
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
              <select name="market-type">
                <option value="">All products</option>
                <option value="sourdough">Sourdough</option>
                <option value="eggs">Eggs</option>
                <option value="other">Other</option>
              </select>
            </label>
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
              </article>
            ))}
          </div>
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
