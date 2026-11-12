import { useState } from 'react'
import type { ReactNode } from 'react'
import type { CatalogCard } from '../services/catalog-contract'
import { publicMediaUrl } from '../services/media'
import { usd } from '../utils/presentation'
import { LeafSprig } from './LeafSprig'
import { SaveFavorite } from '../pages/FavoritesPage'
import './listing.css'
import { HideFromSuggestions } from './HideFromSuggestions'

export function ListingOverview({
  listing,
  children,
}: {
  listing: CatalogCard
  children: ReactNode
}) {
  const { payload, availability } = listing
  return (
    <article className="listing-overview" aria-labelledby="listing-title">
      <ProductGallery photos={payload.photos} />
      <div className="listing-summary">
        <header className="listing-heading">
          <p className="eyebrow">From {payload.seller_display_name}</p>
          <h1 id="listing-title">{payload.product.title}</h1>
          <p className="workspace-muted">
            {payload.location ?? 'No public location provided'}
          </p>
        </header>
        {payload.summary && (
          <section
            className="listing-description"
            aria-labelledby="listing-about"
          >
            <h2 id="listing-about">About this product</h2>
            <p>{payload.summary}</p>
          </section>
        )}
        <section
          className="listing-purchase"
          aria-labelledby="listing-price-label"
        >
          <h2 id="listing-price-label">Price & local pickup</h2>
          <p className="listing-price">
            {usd(payload.price.amount)}{' '}
            <span>per {payload.product.selling_unit}</span>
          </p>
          <p className="workspace-status">
            {availability.status === 'available'
              ? `${availability.available_units} selling units available`
              : availability.status === 'unavailable'
                ? 'Currently unavailable'
                : 'Stock not configured'}
          </p>
          {(payload.selling_quantity || payload.unit_price) && (
            <dl className="listing-unit-details">
              {payload.selling_quantity && (
                <div>
                  <dt>In one selling unit</dt>
                  <dd>
                    {payload.selling_quantity.value}{' '}
                    {payload.selling_quantity.unit}
                  </dd>
                </div>
              )}
              {payload.unit_price && (
                <div>
                  <dt>Standard unit price</dt>
                  <dd>
                    {payload.unit_price.amount === null
                      ? 'Below display precision'
                      : usd(payload.unit_price.amount)}{' '}
                    per {payload.unit_price.reference_unit}
                  </dd>
                </div>
              )}
            </dl>
          )}
          {payload.unit_price && (
            <p className="workspace-muted">
              Unit pricing uses seller-reported quantity.
            </p>
          )}
          <div className="listing-order">{children}</div>
          <div className="listing-pickup-note">
            <p>
              <strong>Local pickup demo</strong>
            </p>
            <p className="workspace-muted">
              No shipping, taxes or delivery charges are calculated.{' '}
              {availability.notice}
            </p>
          </div>
        </section>
        <div className="listing-support-actions">
          <SaveFavorite listingId={listing.id} />
          <HideFromSuggestions listingId={listing.id} />
          <a href={`#/assistant/buyer/${listing.id}`}>
            Ask FairMade about this price <span aria-hidden="true">↗</span>
          </a>
        </div>
      </div>
    </article>
  )
}

function ProductGallery({
  photos,
}: {
  photos: CatalogCard['payload']['photos']
}) {
  const [selected, setSelected] = useState(0)
  const [failed, setFailed] = useState<string | null>(null)
  const photo = photos[selected]
  return (
    <section className="product-gallery" aria-label="Product photos">
      <div className="product-gallery-main">
        {photo && failed !== photo.src ? (
          <img
            src={publicMediaUrl(photo.src)}
            alt={photo.alt_text}
            width={photo.width}
            height={photo.height}
            onError={() => setFailed(photo.src)}
          />
        ) : (
          <div className="product-photo-empty">
            <LeafSprig />
            <p>{photo ? 'Photo unavailable' : 'No product photo yet'}</p>
            <span>
              {photo
                ? 'The seller’s image could not be loaded.'
                : 'The seller hasn’t shared a photo of this product.'}
            </span>
          </div>
        )}
      </div>
      {photos.length > 1 && (
        <div
          className="product-gallery-thumbnails"
          aria-label="Choose product photo"
        >
          {photos.map((item, index) => (
            <button
              key={item.id}
              aria-label={`View product photo ${index + 1}`}
              aria-pressed={selected === index}
              onClick={() => setSelected(index)}
            >
              <img
                src={publicMediaUrl(item.src)}
                alt=""
                loading="lazy"
                width={item.width}
                height={item.height}
              />
            </button>
          ))}
        </div>
      )}
      {photo && (
        <p className="product-photo-caption">
          Photo {selected + 1} of {photos.length} · Seller-provided image
        </p>
      )}
    </section>
  )
}
