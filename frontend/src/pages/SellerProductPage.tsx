import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { ErrorNotice, SignInPrompt } from '../components/Feedback'
import { Field, TextArea } from '../components/FormFields'
import { fieldValue } from '../utils/form'
import { PricingResults } from '../components/PricingResults'
import { PricingPage } from './PricingPage'
import { QualityStep } from './seller/QualityStep'
import { PublishStep } from './seller/PublishStep'
import { ComparisonStep } from './seller/ComparisonStep'
import { useSession } from '../services/session'
import {
  getAnalyses,
  getAnalysis,
  getProduct,
  saveAnalysis,
  updateProduct,
} from '../services/seller'
import type { SellerProduct } from '../services/seller'
import type { PricingResponse } from '../types/pricing'
import { useResource } from '../hooks/useResource'
import { useAction } from '../hooks/useAction'

export function SellerProductPage({ id }: { id: string }) {
  const session = useSession()
  return (
    <WorkspaceLayout
      title="From your hands to the market."
      intro="Your private inputs stay private until you explicitly approve a public snapshot."
    >
      {!session ? (
        <SignInPrompt />
      ) : !session.account.roles.includes('seller') ? (
        <p>
          Seller access is required.{' '}
          <a href="#/account">Check your application.</a>
        </p>
      ) : (
        <ProductWorkspace id={id} />
      )}
    </WorkspaceLayout>
  )
}

function ProductWorkspace({ id }: { id: string }) {
  const resource = useResource(
    useCallback((signal) => getProduct(id, signal), [id]),
  )
  const [step, setStep] = useState<
    'calculate' | 'quality' | 'compare' | 'publish'
  >('calculate')
  const action = useAction()

  function editProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    void action.run(async () => {
      await updateProduct(id, {
        name: fieldValue(form, 'edit-name'),
        selling_unit: fieldValue(form, 'edit-unit'),
        description: fieldValue(form, 'edit-description') || null,
      })
      resource.reload()
    }, 'Product updated. Existing saved analyses and public snapshots remain historical; review them before publishing again.')
  }

  return (
    <>
      <a href="#/seller">← Your products</a>
      <ErrorNotice error={resource.error || action.error} />
      {resource.loading && <p role="status">Loading product…</p>}
      {action.notice && (
        <p role="status" className="calculator-notice">
          {action.notice}
        </p>
      )}
      {resource.data && (
        <>
          <section className="workspace-panel">
            <h2>{resource.data.name}</h2>
            <p>
              {resource.data.selling_unit} · {resource.data.product_type}
            </p>
            <details>
              <summary>Edit private product details</summary>
              <form onSubmit={editProduct}>
                <fieldset className="calculator-form" disabled={action.busy}>
                  <legend className="sr-only">Edit product</legend>
                  <div className="calculator-grid">
                    <Field
                      name="edit-name"
                      title="Name"
                      defaultValue={resource.data.name}
                      required
                      maxLength={200}
                      pattern=".*\S.*"
                    />
                    <Field
                      name="edit-unit"
                      title="Selling unit"
                      defaultValue={resource.data.selling_unit}
                      required
                      maxLength={200}
                      pattern=".*\S.*"
                    />
                    <TextArea
                      name="edit-description"
                      title="Private description"
                      defaultValue={resource.data.description ?? ''}
                      maxLength={2000}
                    />
                  </div>
                  <div className="workspace-actions">
                    <button className="calculator-secondary" type="submit">
                      Save private details
                    </button>
                  </div>
                </fieldset>
              </form>
            </details>
          </section>
          <nav className="workspace-actions" aria-label="Product workflow">
            <button
              className="calculator-secondary"
              aria-current={step === 'calculate' ? 'step' : undefined}
              onClick={() => setStep('calculate')}
            >
              1 · Calculate
            </button>
            <button
              className="calculator-secondary"
              aria-current={step === 'quality' ? 'step' : undefined}
              onClick={() => setStep('quality')}
            >
              2 · Quality Lock
            </button>
            <button
              className="calculator-secondary"
              aria-current={step === 'compare' ? 'step' : undefined}
              onClick={() => setStep('compare')}
            >
              3 · Compare (optional)
            </button>
            <button
              className="calculator-secondary"
              aria-current={step === 'publish' ? 'step' : undefined}
              onClick={() => setStep('publish')}
            >
              4 · Review & publish
            </button>
          </nav>
          {step === 'calculate' && <CostStep product={resource.data} />}
          {step === 'quality' && <QualityStep productId={id} />}
          {step === 'compare' && <ComparisonStep product={resource.data} />}
          {step === 'publish' && <PublishStep product={resource.data} />}
        </>
      )}
      {Boolean(resource.error) && (
        <button className="calculator-secondary" onClick={resource.reload}>
          Retry
        </button>
      )}
    </>
  )
}

function CostStep({ product }: { product: SellerProduct }) {
  const saved = useResource(
    useCallback((signal) => getAnalyses(product.id, signal), [product.id]),
  )
  const [historical, setHistorical] = useState<{
    result: PricingResponse
    unit: string
  } | null>(null)
  const [savedId, setSavedId] = useState('')
  const action = useAction()

  return (
    <>
      <section className="workspace-panel">
        <h2>Your saved cost picture</h2>
        <ErrorNotice error={saved.error || action.error} />
        {saved.loading && <p role="status">Loading saved analyses…</p>}
        {saved.data &&
          (saved.data.items.length ? (
            <label className="calculator-field">
              Review one of the latest 100 analyses
              <select
                value={savedId}
                disabled={action.busy}
                onChange={(event) => {
                  const id = event.target.value
                  setSavedId(id)
                  setHistorical(null)
                  if (id)
                    void action.run(async () => {
                      const analysis = await getAnalysis(product.id, id)
                      setHistorical({
                        result: analysis.result,
                        unit: analysis.product_snapshot.selling_unit,
                      })
                    })
                }}
              >
                <option value="">Choose a saved analysis</option>
                {saved.data.items.map((analysis) => (
                  <option value={analysis.id} key={analysis.id}>
                    {new Date(analysis.created_at).toLocaleString()} ·{' '}
                    {analysis.id.slice(0, 8)}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <p>No saved analyses yet. Add your batch inputs below.</p>
          ))}
        {historical && (
          <PricingResults result={historical.result} unit={historical.unit} />
        )}
      </section>
      <PricingPage
        product={product}
        onAnalyze={async (request, signal) => {
          const analysis = await saveAnalysis(product.id, request, signal)
          saved.reload()
          setSavedId(analysis.id)
          setHistorical(null)
          if (analysis.product_snapshot.selling_unit !== product.selling_unit)
            throw new Error(
              'Your product unit changed while saving. The analysis was saved privately; reload the product to review its correct unit.',
            )
          return analysis.result
        }}
      />
      <p>
        Saved analyses are immutable and private. Choose Quality Lock next to
        protect your requirements, then review what to publish.
      </p>
    </>
  )
}
