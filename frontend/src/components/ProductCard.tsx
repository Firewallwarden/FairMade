import { useState } from 'react'
import type { Product } from '../types/product'

const usd = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

export function ProductCard({ product }: { product: Product }) {
  const [failedImage, setFailedImage] = useState<string | null>(null)
  return (
    <article className="product-card">
      <div className="product-image">
        {failedImage === product.image ? (
          <div className="image-fallback">{product.name}</div>
        ) : (
          <img
            src={product.image}
            alt={product.imageAlt}
            loading="lazy"
            width="600"
            height="700"
            onError={() => setFailedImage(product.image)}
            onLoad={() => setFailedImage(null)}
          />
        )}
        <span>{product.category}</span>
      </div>
      <p className="product-maker">{product.maker}</p>
      <div className="product-title">
        <h3>{product.name}</h3>
        <span>{usd.format(product.price)}</span>
      </div>
      <p className="product-note">{product.note}</p>
    </article>
  )
}
