import { HistorySelection } from '../../components/HistorySelection'
import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { Field, TextArea } from '../../components/FormFields'
import { fieldValue } from '../../utils/form'
import { ErrorNotice } from '../../components/Feedback'
import { PassportView } from '../../components/PassportView'
import { CatalogPreview } from '../../components/CatalogPreview'
import { useResource } from '../../hooks/useResource'
import { useAction } from '../../hooks/useAction'
import { costCategories } from '../../types/pricing'
import { PhotoSelection } from './PresentationStep'
import {
  activateListing,
  createPassport,
  createReview,
  deactivateListing,
  getAnalyses,
  getEvaluations,
  getInventory,
  getListing,
  getListingPreview,
  getPassportDrafts,
  getPassportPreview,
  getPublications,
  publishPassport,
  saveInventory,
  saveListing,
} from '../../services/seller'
import type { SellerProduct } from '../../services/seller'
import { getComparisons } from '../../services/comparisons'
import { comparisonUnits, sellingUnits } from '../../types/contracts'
import { choice } from '../../services/decode'
import { CompositionFields } from './CompositionFields'
import { readComposition } from '../../utils/composition'
import { PassportPublications } from './PassportPublications'
import { getCatalogListing } from '../../services/commerce'
import { ApiError } from '../../services/http'

import { PassportEditor } from './PassportEditor'
import { getPassportDraft } from '../../services/seller'

const disclosureLabels = {
  include_labor: 'Labor cost per unit',
  include_unit_cost: 'Total production cost per unit',
  include_quality_requirements: 'Quality Lock requirements',
  include_quality_summary:
    'Quality claim-check summary, including failures and uncertainty',
  include_market_context: 'Available comparison context',
}

export function PublishStep({ product }: { product: SellerProduct }) {
  const resource = useResource(
    useCallback(
      async (signal) => {
        const [analyses, evaluations, inventory, listing, drafts, comparisons] =
          await Promise.all([
            getAnalyses(product.id, signal),
            getEvaluations(product.id, signal),
            getInventory(product.id, signal),
            getListing(product.id, signal),
            getPassportDrafts(product.id, signal),
            getComparisons(product.id, signal),
          ])
        return {
          analyses,
          evaluations,
          inventory,
          listing,
          drafts,
          comparisons,
        }
      },
      [product.id],
    ),
  )
  const action = useAction()
  const [review, setReview] = useState<Awaited<
    ReturnType<typeof createReview>
  > | null>(null)
  const [draftId, setDraftId] = useState('')
  const [editableDraft, setEditableDraft] = useState<Awaited<ReturnType<typeof getPassportDraft>> | null>(null)
  const [draftSaved, setDraftSaved] = useState(false)
  const [preview, setPreview] = useState<Awaited<
    ReturnType<typeof getPassportPreview>
  > | null>(null)
  const [publication, setPublication] = useState('')
  const [passportWithdrawn, setPassportWithdrawn] = useState(false)
  const [listingPreview, setListingPreview] = useState<Awaited<
    ReturnType<typeof getListingPreview>
  > | null>(null)
  const [listing, setListing] =
    useState<Awaited<ReturnType<typeof getListing>>>(null)
  const [inventory, setInventory] = useState<Awaited<
    ReturnType<typeof getInventory>
  > | null>(null)
  const [publishedListing, setPublishedListing] = useState('')
  const candidateListing = listing ?? resource.data?.listing
  const publicListing = useResource(useCallback(async (signal) => {
    if (!candidateListing || passportWithdrawn ||
      (publication && candidateListing.content.passport_publication_id !== publication)) return null
    try {
      return await getCatalogListing(candidateListing.id, signal)
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null
      throw error
    }
  }, [candidateListing, passportWithdrawn, publication]))

  function makePassport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    void action.run(async () => {
      const composition = readComposition(fields)
      setEditableDraft(null)
      setPreview(null)
      setPublication('')
      setListingPreview(null)
      const selectedEvaluations = fields.getAll('evaluation').map(String)
      const comparison = fieldValue(fields, 'review-comparison') || null
      const quantityValue = fieldValue(fields, 'review-unit-quantity')
      const quantityUnit = fieldValue(fields, 'review-unit-type')
      if (Boolean(quantityValue) !== Boolean(quantityUnit))
        throw new Error(
          'Provide both production-unit quantity and unit, or leave both blank.',
        )
      if (quantityValue && !comparison)
        throw new Error(
          'Choose a comparison report before adding a production-unit mapping.',
        )
      const savedReview = await createReview(
        product.id,
        fieldValue(fields, 'review-analysis'),
        selectedEvaluations,
        comparison,
        quantityValue
          ? {
              value: quantityValue,
              unit: choice(quantityUnit, comparisonUnits),
            }
          : undefined,
      )
      setReview(savedReview)
      const disclosures = Object.fromEntries(
        Object.keys(disclosureLabels).map((key) => [key, fields.has(key)]),
      )
      const draft = await createPassport(product.id, {
        review_id: savedReview.id,
        title: fieldValue(fields, 'passport-title'),
        price: fieldValue(fields, 'passport-price'),
        public_description: fieldValue(fields, 'passport-description') || null,
        composition,
        disclosures: {
          ...disclosures,
          include_composition: fields.has('include_composition'),
          cost_categories: costCategories.filter((category) =>
            fields.getAll('cost-disclosure').includes(category),
          ),
        },
      })
      setDraftId(draft.id)
      setPreview(await getPassportPreview(product.id, draft.id))
    }, 'Private draft created. Review the exact public preview before approving publication.')
  }

  function approvePassport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const approved = new FormData(event.currentTarget).has('approve-passport')
    if (!preview || !approved) return
    void action.run(async () => {
      const published = await publishPassport(
        product.id,
        draftId,
        preview.revision,
        preview.preview_hash,
      )
      setPublication(published.id)
      setPassportWithdrawn(false)
    }, 'Passport published with the exact disclosures you approved. Your listing still needs separate approval.')
  }

  function prepareListing(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    const current = listing ?? resource.data?.listing
    void action.run(async () => {
      const photoIds = fields.getAll('listing-photo').map(String)
      if (photoIds.length > 6)
        throw new Error('Choose at most six photos for a listing.')
      const photos =
        fields.get('photo-selection-loaded') === 'yes'
          ? photoIds.map((photo_id) => {
              const alt_text = fieldValue(fields, `photo-alt-${photo_id}`)
              if (!alt_text)
                throw new Error(
                  'Every selected photo needs meaningful alt text.',
                )
              return { photo_id, alt_text }
            })
          : (current?.content.photos ?? null)
      const saved = await saveListing(
        product.id,
        {
          passport_publication_id: publication,
          seller_display_name: fieldValue(fields, 'listing-seller'),
          location: fieldValue(fields, 'listing-location') || null,
          summary: fieldValue(fields, 'listing-summary') || null,
          selling_quantity: {
            value: fieldValue(fields, 'listing-quantity'),
            unit: choice(
              fieldValue(fields, 'listing-quantity-unit'),
              sellingUnits,
            ),
          },
          photos,
          ...(current && { expected_revision: current.revision }),
        },
        current?.revision,
      )
      setListing(saved)
      setListingPreview(await getListingPreview(product.id))
    }, 'Listing draft saved. Review and explicitly approve it below.')
  }

  return (
    <div>
      <ErrorNotice error={resource.error || action.error || publicListing.error} />
      {action.notice && (
        <p className="calculator-notice" role="status">
          {action.notice}
        </p>
      )}
      {resource.loading && <p role="status">Loading publication sources…</p>}
      {Boolean(resource.error) && (
        <button className="calculator-secondary" onClick={resource.reload}>
          Reload sources
        </button>
      )}
      {resource.data && (
        <>
          <section className="workspace-panel">
            <h2>First, your private stock.</h2>
            <p>
              Stock counts use {product.selling_unit}. Reserved stock is held
              for existing orders. Updating total on-hand stock must still cover
              reservations.
            </p>
            <p>
              On hand: {(inventory ?? resource.data.inventory).on_hand} ·
              Reserved: {(inventory ?? resource.data.inventory).reserved} ·
              Available: {(inventory ?? resource.data.inventory).available}
            </p>
            <form
              onSubmit={(event) => {
                event.preventDefault()
                const count = Number(
                  new FormData(event.currentTarget).get('stock-count'),
                )
                const currentInventory = inventory ?? resource.data?.inventory
                if (currentInventory)
                  void action.run(
                    async () =>
                      setInventory(
                        await saveInventory(
                          product.id,
                          currentInventory.revision,
                          product.selling_unit,
                          count,
                        ),
                      ),
                    'Stock saved.',
                  )
              }}
            >
              <fieldset disabled={action.busy} className="calculator-form">
                <legend className="sr-only">Set inventory</legend>
                <Field
                  name="stock-count"
                  title="Total on hand (selling units)"
                  type="number"
                  min="0"
                  max="1000000"
                  step="1"
                  required
                  defaultValue={(inventory ?? resource.data.inventory).on_hand}
                />
                <div className="workspace-actions">
                  <button className="calculator-secondary" type="submit">
                    Save stock
                  </button>
                </div>
              </fieldset>
            </form>
          </section>
          <section className="workspace-panel">
            <p className="eyebrow">Seller controls the final price</p>
            <h2>Choose the story your price tells.</h2>
            <p>
              All disclosures start off. Select only the information you want
              made public. Raw private ingredients, labor entries and recipes
              stay private. Only a separate composition declaration you author
              and approve can describe public finished-product contents.
            </p>
            {!resource.data.analyses.items.length ? (
              <p>
                Save a cost analysis in Calculate before creating a Passport.
              </p>
            ) : (
              <form
                onSubmit={makePassport}
                onChange={() => {
                  setPreview(null)
                  setPublication('')
                  setListingPreview(null)
                  setDraftId('')
                  setEditableDraft(null)
                  setReview(null)
                }}
              >
                <fieldset className="calculator-form" disabled={action.busy}>
                  <legend className="sr-only">
                    Create pricing review and Passport draft
                  </legend>
                  <HistorySelection disabled={action.busy} productId={product.id} kind="analyses" title="Saved analysis" name="review-analysis" required />
                  <details>
                    <summary>
                      Include saved local comparison context (optional)
                    </summary>
                    <HistorySelection disabled={action.busy} productId={product.id} kind="price-comparisons" title="Comparison report" name="review-comparison" />
                    <p>
                      To relate your production-unit prices to these
                      observations, explicitly declare the quantity represented
                      by one selling unit. Without this declaration, no
                      production-price comparison is established.
                    </p>
                    <div className="calculator-grid">
                      <Field
                        name="review-unit-quantity"
                        title="Quantity per production unit (optional)"
                        type="number"
                        min="0.000001"
                        max="1000000000"
                        step="0.000001"
                      />
                      <label className="calculator-field">
                        Quantity unit
                        <select name="review-unit-type">
                          <option value="">No declaration</option>
                          {['g', 'kg', 'egg', 'dozen', 'loaf', 'item'].map(
                            (unit) => (
                              <option key={unit}>{unit}</option>
                            ),
                          )}
                        </select>
                      </label>
                    </div>
                  </details>
                  <h3>Quality evidence to include in the private review</h3>
                  {!resource.data.evaluations.items.length && (
                    <p>
                      No saved claim checks. The review will report missing
                      quality evidence.
                    </p>
                  )}
                  <HistorySelection disabled={action.busy} productId={product.id} kind="quality-evaluations" title="Saved quality evaluations" name="evaluation" multiple />
                  <div className="calculator-grid">
                    <Field
                      name="passport-title"
                      title="Public product title"
                      required
                      maxLength={200}
                      pattern=".*\S.*"
                      defaultValue={product.name}
                    />
                    <Field
                      name="passport-price"
                      title="Your chosen selling price (USD per unit)"
                      type="number"
                      min="0.01"
                      max="1000000000"
                      step="0.01"
                      required
                    />
                    <TextArea
                      name="passport-description"
                      title="Public description (optional)"
                      maxLength={2000}
                    />
                  </div>
                  <h3>Cost categories to disclose per unit</h3>
                  {costCategories.map((category) => (
                    <label className="workspace-check" key={category}>
                      <input
                        type="checkbox"
                        name="cost-disclosure"
                        value={category}
                      />
                      {category.replaceAll('_', ' ')}
                    </label>
                  ))}
                  <h3>Other disclosures</h3>
                  <CompositionFields
                    onEdit={() => {
                      setPreview(null)
                      setPublication('')
                      setListingPreview(null)
                      setDraftId('')
                      setReview(null)
                    }}
                  />
                  {Object.entries(disclosureLabels).map(([key, label]) => (
                    <label className="workspace-check" key={key}>
                      <input type="checkbox" name={key} />
                      {label}
                    </label>
                  ))}
                  <div className="workspace-actions">
                    <button type="submit" className="button-primary">
                      Build private review & preview
                    </button>
                  </div>
                </fieldset>
              </form>
            )}
            <details>
              <summary>
                Recover a previous Passport draft or publication
              </summary>
              <HistorySelection disabled={action.busy} productId={product.id} kind="passports" title="Passport drafts" value={draftId} onSelect={(id) => {

                    setDraftId(id)
                    setEditableDraft(null)
                    setDraftSaved(false)
                    setPreview(null)
                    setPublication('')
                    setListingPreview(null)
                    if (id)
                      void action.run(async () => {
                        setEditableDraft(await getPassportDraft(product.id, id))
                        setDraftSaved(true)
                        setPreview(await getPassportPreview(product.id, id))
                        const publications = await getPublications(
                          product.id,
                          id,
                        )
                        const active = publications.items.find(
                          (item) => item.state === 'published',
                        )
                        setPublication(active?.id ?? '')
                        setPassportWithdrawn(!active)
                      })
                  }} />
              <button
                className="calculator-secondary"
                disabled={action.busy}
                onClick={resource.reload}
              >
                Refresh saved drafts
              </button>
            </details>
          </section>
        </>
      )}
      {review && (
        <section className="workspace-panel">
          <h2>Your private pricing explanation</h2>
          <ul>
            {review.explanations.map((explanation, index) => (
              <li key={index}>{explanation}</li>
            ))}
          </ul>
          <p>
            No LLM provider or external lookup is used. Failed Quality Locks
            cannot be presented as acceptable savings.
          </p>
        </section>
      )}
      {editableDraft && <>
        <PassportEditor key={editableDraft.id} productId={product.id} draft={editableDraft}
          onEdit={() => {
            setPreview(null)
            setPublication('')
            setListingPreview(null)
            setDraftSaved(false)
          }}
          onSaved={(saved) => {
            setEditableDraft(saved)
            setDraftSaved(true)
            resource.reload()
          }} />
        <button className="calculator-secondary" disabled={action.busy || !draftSaved} onClick={() => {
          setPreview(null)
          void action.run(async () => setPreview(await getPassportPreview(product.id, editableDraft.id)))
        }}>Generate fresh Passport preview</button>
      </>}
      {preview && (
        <>
          <PassportView passport={preview.payload} />
          {!publication && (
            <form onSubmit={approvePassport} className="workspace-panel">
              <label className="workspace-check">
                <input
                  key={preview.preview_hash}
                  name="approve-passport"
                  type="checkbox"
                  required
                  disabled={action.busy}
                />
                I approve publishing this exact Passport and its selected
                disclosures. Public copies cannot be recalled.
              </label>
              <div className="workspace-actions">
                <button
                  type="submit"
                  className="button-primary"
                  disabled={action.busy}
                >
                  Publish approved Passport
                </button>
              </div>
            </form>
          )}
        </>
      )}
      {draftId && <PassportPublications key={draftId} productId={product.id} draftId={draftId} onWithdrawn={() => {
        setPublication('')
        setPreview(null)
        setListingPreview(null)
        setPublishedListing('')
        setListing(null)
        setPassportWithdrawn(true)
        resource.reload()
      }} />}
      {publication && (
        <section className="workspace-panel">
          <h2>Give it a place at the market.</h2>
          <p>
            Your approved Passport is published. Choose the public seller name
            and an approximate location label, then preview the listing. Do not
            put a private address here.
          </p>
          <form
            onSubmit={prepareListing}
            onChange={() => setListingPreview(null)}
          >
            <fieldset disabled={action.busy} className="calculator-form">
              <legend className="sr-only">
                Create or update listing draft
              </legend>
              <div className="calculator-grid">
                <Field
                  name="listing-seller"
                  title="Public seller display name"
                  required
                  maxLength={200}
                  pattern=".*\S.*"
                  defaultValue={
                    resource.data?.listing?.content.seller_display_name
                  }
                />
                <Field
                  name="listing-location"
                  title="Approximate public location (optional)"
                  maxLength={200}
                  defaultValue={resource.data?.listing?.content.location ?? ''}
                />
                <TextArea
                  name="listing-summary"
                  title="Public listing summary (optional)"
                  maxLength={1000}
                  defaultValue={resource.data?.listing?.content.summary ?? ''}
                />
                <Field
                  name="listing-quantity"
                  title="Quantity contained in one selling unit"
                  type="number"
                  min="0.000001"
                  max="1000000000"
                  step="0.000001"
                  required
                  defaultValue={
                    resource.data?.listing?.content.selling_quantity?.value
                  }
                />
                <label className="calculator-field">
                  Quantity unit
                  <select
                    name="listing-quantity-unit"
                    defaultValue={
                      resource.data?.listing?.content.selling_quantity?.unit ??
                      (product.product_type === 'eggs'
                        ? 'dozen'
                        : product.product_type === 'sourdough'
                          ? 'loaf'
                          : 'item')
                    }
                  >
                    {['g', 'kg', 'ml', 'l', 'egg', 'dozen', 'loaf', 'item'].map(
                      (unit) => (
                        <option key={unit} value={unit}>
                          {unit}
                        </option>
                      ),
                    )}
                  </select>
                </label>
              </div>
              <p>
                For one loaf, enter 1 loaf. For a dozen eggs, enter 1 dozen. The
                backend normalizes this declared quantity; it is not
                independently measured.
              </p>
              <PhotoSelection
                productId={product.id}
                selected={
                  (listing ?? resource.data?.listing)?.content.photos ?? []
                }
              />
              <div className="workspace-actions">
                <button type="submit" className="button-primary">
                  Save & preview listing
                </button>
              </div>
            </fieldset>
          </form>
        </section>
      )}
      {listingPreview && (
        <>
          <CatalogPreview content={listingPreview.payload} productId={product.id} />
          {listingPreview.publication_blockers.length > 0 && (
            <p role="alert">
              Publication is blocked:{' '}
              {listingPreview.publication_blockers.join(', ')}. Update the
              listing and preview again.
            </p>
          )}
          <form
            className="workspace-panel"
            onSubmit={(event) => {
              event.preventDefault()
              if (!new FormData(event.currentTarget).has('approve-listing'))
                return
              void action.run(async () => {
                const active = await activateListing(
                  product.id,
                  listingPreview.revision,
                  listingPreview.preview_hash,
                )
                setListing(active)
                setPublishedListing(active.id)
              }, 'Your approved listing is active in the marketplace.')
            }}
          >
            <label className="workspace-check">
              <input
                type="checkbox"
                name="approve-listing"
                key={listingPreview.preview_hash}
                required
                disabled={action.busy}
              />
              I approve this exact public listing and linked Passport.
            </label>
            <div className="workspace-actions">
              <button
                type="submit"
                className="button-primary"
                disabled={
                  action.busy || listingPreview.publication_blockers.length > 0
                }
              >
                Publish approved listing
              </button>
            </div>
          </form>
        </>
      )}
      {publicListing.data && !passportWithdrawn && (publishedListing || resource.data?.listing?.state === 'active') && (
        <div className="workspace-panel">
          <h2>Your goods are at the market.</h2>
          <a
            className="button-primary"
            href={`#/market/${publishedListing || resource.data?.listing?.id}`}
          >
            View public listing
          </a>
          <div className="workspace-actions">
            <button
              className="calculator-secondary"
              disabled={action.busy}
              onClick={() =>
                action.run(async () => {
                  await deactivateListing(product.id)
                  setPublishedListing('')
                  setListingPreview(null)
                  resource.reload()
                }, 'Listing hidden. Existing order snapshots remain historical.')
              }
            >
              Hide listing
            </button>
          </div>
        </div>
      )}
      <div className="workspace-actions">
        <button
          className="calculator-secondary"
          disabled={action.busy}
          onClick={() => {
            setInventory(null)
            setListing(null)
            setListingPreview(null)
            resource.reload()
          }}
        >
          Refresh current stock and drafts
        </button>
      </div>
    </div>
  )
}
