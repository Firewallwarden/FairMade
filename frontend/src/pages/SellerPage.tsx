import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { ErrorNotice, SignInPrompt } from '../components/Feedback'
import { Field, TextArea } from '../components/FormFields'
import { fieldValue } from '../utils/form'
import { useSession } from '../services/session'
import { createProduct, getProducts } from '../services/seller'
import { useResource } from '../hooks/useResource'
import { useAction } from '../hooks/useAction'
import { productTypes } from '../types/contracts'
import { choice } from '../services/decode'

export function SellerPage() {
  const session = useSession()
  return (
    <WorkspaceLayout
      title="Small batches. Worth every bit."
      intro="Create a product, account for your work, protect your standards, and choose what to share."
    >
      {!session ? (
        <SignInPrompt />
      ) : !session.account.roles.includes('seller') ? (
        <div className="workspace-empty">
          <h2>Your seller journey starts here.</h2>
          <p>
            Seller access requires manual approval. You can request access and
            check its status from your account.
          </p>
          <a className="button-primary" href="#/account">
            View seller application
          </a>
        </div>
      ) : (
        <SellerDashboard />
      )}
    </WorkspaceLayout>
  )
}

function SellerDashboard() {
  const [offset, setOffset] = useState(0)
  const resource = useResource(
    useCallback((signal) => getProducts(offset, signal), [offset]),
  )
  const action = useAction()

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    void action.run(async () => {
      const product = await createProduct({
        name: fieldValue(fields, 'product-name'),
        product_type: choice(fieldValue(fields, 'product-type'), productTypes),
        selling_unit: fieldValue(fields, 'product-unit'),
        description: fieldValue(fields, 'product-description') || null,
      })
      window.location.hash = `/seller/${product.id}`
    })
  }

  return (
    <>
      <ol className="workspace-steps">
        <li>Create</li>
        <li>Calculate</li>
        <li>Review</li>
        <li>Publish</li>
      </ol>
      <div className="workspace-actions">
        <a className="calculator-secondary" href="#/receipts">
          Receipts & expenses
        </a>
        <a className="calculator-secondary" href="#/storefront/settings">
          Manage your storefront
        </a>
      </div>
      <section className="workspace-panel">
        <h2>Something made with care.</h2>
        <p>
          Start a private product. Creating one does not publish any costs or
          listing.
        </p>
        <ErrorNotice error={action.error} />
        <form onSubmit={submit}>
          <fieldset className="calculator-form" disabled={action.busy}>
            <legend className="sr-only">Create a private product</legend>
            <div className="calculator-grid">
              <Field
                title="Product name"
                name="product-name"
                required
                maxLength={200}
                pattern=".*\S.*"
              />
              <label className="calculator-field" htmlFor="product-type">
                Product type
                <select id="product-type" name="product-type">
                  <option value="sourdough">Sourdough</option>
                  <option value="eggs">Eggs</option>
                  <option value="other">Other</option>
                </select>
              </label>
              <Field
                title="One selling unit"
                name="product-unit"
                required
                maxLength={200}
                pattern=".*\S.*"
                placeholder="e.g. one loaf or one dozen eggs"
              />
              <TextArea
                title="Private product description (optional)"
                name="product-description"
                maxLength={2000}
              />
            </div>
            <div className="workspace-actions">
              <button type="submit" className="button-primary">
                {action.busy ? 'Creating…' : 'Create private product'}
              </button>
            </div>
          </fieldset>
        </form>
      </section>
      <section aria-labelledby="products-heading">
        <h2 id="products-heading">Your products</h2>
        <ErrorNotice error={resource.error} />
        {resource.loading ? (
          <p role="status">Loading your products…</p>
        ) : (
          resource.data && (
            <>
              {!resource.data.items.length && (
                <div className="workspace-empty">
                  No products on this page. Create your first batch above.
                </div>
              )}
              <div className="workspace-grid">
                {resource.data.items.map((product) => (
                  <article className="workspace-panel" key={product.id}>
                    <span className="workspace-status">
                      {product.product_type}
                    </span>
                    <h3>{product.name}</h3>
                    <p>Sold as {product.selling_unit}.</p>
                    <p>{product.description}</p>
                    <a
                      className="button-primary"
                      href={`#/seller/${product.id}`}
                    >
                      Open product
                    </a>
                  </article>
                ))}
              </div>
              <div className="workspace-actions">
                <button
                  className="calculator-secondary"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - 20))}
                >
                  Previous
                </button>
                <button
                  className="calculator-secondary"
                  disabled={resource.data.items.length < 20}
                  onClick={() => setOffset(offset + 20)}
                >
                  Next
                </button>
              </div>
            </>
          )
        )}
        <button className="calculator-secondary" onClick={resource.reload}>
          Refresh products
        </button>
      </section>
    </>
  )
}
