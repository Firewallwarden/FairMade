import type { decodeCatalogContent } from '../services/catalog-contract'
import { usd } from '../utils/presentation'
import { publicMediaUrl } from '../services/media'

export function CatalogPreview({
  content,
}: {
  content: ReturnType<typeof decodeCatalogContent>
}) {
  return (
    <section className="workspace-panel" aria-label="Public listing preview">
      <p className="eyebrow">Exact public listing preview</p>
      <h2>{content.product.title}</h2>
      <p>
        {content.seller_display_name}
        {content.location ? ` · ${content.location}` : ''}
      </p>
      <p>{content.summary}</p>
      <p>{content.product.description}</p>
      <p>
        <strong>{usd(content.price.amount)}</strong> per{' '}
        {content.product.selling_unit} · {content.product.product_type}
      </p>
      {content.selling_quantity && (
        <p>
          One selling unit contains {content.selling_quantity.value}{' '}
          {content.selling_quantity.unit}.
        </p>
      )}
      {content.unit_price && (
        <p>
          Standard unit price:{' '}
          {content.unit_price.amount === null
            ? 'Below display precision'
            : usd(content.unit_price.amount)}{' '}
          per {content.unit_price.reference_unit} · seller-reported quantity.
        </p>
      )}
      <div className="listing-gallery">
        {content.photos.map((photo) => (
          <figure key={photo.id}>
            <img
              src={publicMediaUrl(photo.src)}
              alt={photo.alt_text}
              width={photo.width}
              height={photo.height}
            />
            <figcaption>{photo.alt_text}</figcaption>
          </figure>
        ))}
      </div>
      <p>Linked Passport: {content.passport_id}</p>
      <ul>
        {content.notices.map((notice, index) => (
          <li key={index}>{notice}</li>
        ))}
      </ul>
    </section>
  )
}
