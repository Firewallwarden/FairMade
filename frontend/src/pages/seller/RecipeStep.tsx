import { useCallback, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Field, TextArea } from '../../components/FormFields'
import { BatchEntries } from '../../components/BatchEntries'
import { PricingResults } from '../../components/PricingResults'
import { ErrorNotice } from '../../components/Feedback'
import { EvidenceDetails } from '../../components/EvidenceDetails'
import { useResource } from '../../hooks/useResource'
import { useAction } from '../../hooks/useAction'
import {
  getRecipe,
  saveRecipe,
  getRecipeCostings,
  createRecipeCosting,
  getRecipeCosting,
} from '../../services/production'
import { getAnalysis } from '../../services/seller'
import type { SellerProduct } from '../../services/seller'
import { recipeUnits } from '../../services/production-contract'
import type { RecipeData } from '../../services/production-contract'
import { percentToRate } from '../../services/pricing-contract'
import { choice } from '../../services/decode'
import { fieldValue } from '../../utils/form'
import { readBatchEntries, rateAsPercent } from '../../utils/batch-entries'
import { usd } from '../../utils/presentation'

type SavedCosting = {
  costing: Awaited<ReturnType<typeof getRecipeCosting>>
  analysis: Awaited<ReturnType<typeof getAnalysis>>
}
export function RecipeStep({ product }: { product: SellerProduct }) {
  const [offset, setOffset] = useState(0)
  const resource = useResource(
    useCallback(
      async (signal) => {
        const [recipe, costings] = await Promise.all([
          getRecipe(product.id, signal),
          getRecipeCostings(product.id, offset, signal),
        ])
        return { recipe, costings }
      },
      [product.id, offset],
    ),
  )
  const [selected, setSelected] = useState<SavedCosting | null>(null)
  const action = useAction()
  async function show(costing: Awaited<ReturnType<typeof getRecipeCosting>>) {
    setSelected({
      costing,
      analysis: await getAnalysis(product.id, costing.pricing_analysis_id),
    })
  }
  return (
    <section className="workspace-panel">
      <h2>A recipe for understanding your costs.</h2>
      <p>
        Record raw ingredient/input use, including waste, and what you paid for
        the purchase quantity. The backend allocates costs deterministically.
        This is private production information, not the finished-product
        composition shown to buyers.
      </p>
      <ErrorNotice error={resource.error || action.error} />
      {resource.loading && (
        <p role="status">Loading saved recipe and costing history…</p>
      )}
      {resource.data && (
        <RecipeEditor
          key={resource.data.recipe?.revision ?? 'new'}
          product={product}
          saved={resource.data.recipe}
          onSaved={resource.reload}
          onCosted={async (costing) => {
            await show(costing)
            resource.reload()
          }}
        />
      )}
      <details>
        <summary>Saved recipe costings (20 per page)</summary>
        {resource.data?.costings.items.map((item) => (
          <div className="workspace-actions" key={item.id}>
            <span>
              {new Date(item.created_at).toLocaleString()} · recipe revision{' '}
              {item.recipe_revision}
            </span>
            <button
              className="calculator-secondary"
              disabled={action.busy}
              onClick={() =>
                action.run(async () =>
                  show(await getRecipeCosting(product.id, item.id)),
                )
              }
            >
              Review saved costing
            </button>
          </div>
        ))}
        {resource.data && !resource.data.costings.items.length && (
          <p>No saved costings on this page.</p>
        )}
        <div className="workspace-actions">
          <button
            className="calculator-secondary"
            disabled={!offset}
            onClick={() => setOffset(offset - 20)}
          >
            Previous costings
          </button>
          <button
            className="calculator-secondary"
            disabled={(resource.data?.costings.items.length ?? 0) < 20}
            onClick={() => setOffset(offset + 20)}
          >
            Next costings
          </button>
        </div>
      </details>
      {selected && (
        <section className="workspace-panel">
          <p className="eyebrow">
            Historical saved costing · Recipe revision{' '}
            {selected.costing.recipe_revision}
          </p>
          <h3>Allocated raw-input costs</h3>
          <ul>
            {selected.costing.ingredients.map((item, index) => (
              <li key={index}>
                {item.label}: {usd(item.allocated_cost)}
              </li>
            ))}
          </ul>
          <p>
            Total allocated materials: {usd(selected.costing.materials_total)}.
          </p>
          <ul>
            {selected.costing.warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
          <PricingResults
            result={selected.analysis.result}
            unit={selected.analysis.product_snapshot.selling_unit}
          />
          <details>
            <summary>Exact private recipe snapshot</summary>
            <EvidenceDetails value={selected.costing.snapshot} />
          </details>
          <p>
            This saved analysis can be selected in Review & publish. It does not
            update an existing public listing or stock.
          </p>
        </section>
      )}
      <button
        className="calculator-secondary"
        disabled={action.busy}
        onClick={resource.reload}
      >
        Reload saved recipe and costings
      </button>
    </section>
  )
}
function RecipeEditor({
  product,
  saved,
  onSaved,
  onCosted,
}: {
  product: SellerProduct
  saved: Awaited<ReturnType<typeof getRecipe>>
  onSaved: () => void
  onCosted: (
    value: Awaited<ReturnType<typeof createRecipeCosting>>,
  ) => Promise<void>
}) {
  const [ingredients, setIngredients] = useState(() =>
    (
      saved?.content.ingredients ?? [
        {
          label: '',
          quantity: { value: '', unit: 'g' as const },
          purchase_quantity: { value: '', unit: 'g' as const },
          purchase_cost: '',
          cost_recorded_on: '',
        },
      ]
    ).map((item) => ({ ...item, key: crypto.randomUUID() })),
  )
  const [dirty, setDirty] = useState(false),
    [today] = useState(() => new Date().toISOString().slice(0, 10))
  const action = useAction(),
    costAttempt = useRef<string | null>(null)
  function edited() {
    setDirty(true)
  }
  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    void action.run(async () => {
      const value = (name: string) => fieldValue(fields, name),
        batch = readBatchEntries(fields, 'recipe')
      const content: RecipeData = {
        name: value('recipe-name'),
        currency: 'USD',
        sellable_units: Number(value('recipe-yield')),
        ingredients: ingredients.map((row) => ({
          label: value(`recipe-input-label-${row.key}`),
          quantity: {
            value: value(`recipe-input-used-${row.key}`),
            unit: choice(
              value(`recipe-input-used-unit-${row.key}`),
              recipeUnits,
            ),
          },
          purchase_quantity: {
            value: value(`recipe-input-bought-${row.key}`),
            unit: choice(
              value(`recipe-input-bought-unit-${row.key}`),
              recipeUnits,
            ),
          },
          purchase_cost: value(`recipe-input-price-${row.key}`),
          cost_recorded_on: value(`recipe-input-date-${row.key}`),
        })),
        other_costs: batch.costs,
        labor: batch.labor,
        payment_fees: {
          rate: percentToRate(value('recipe-fee-percent')),
          fixed_per_order: value('recipe-fee-fixed'),
          units_per_order: Number(value('recipe-fee-units')),
        },
        target_margin: {
          minimum: percentToRate(value('recipe-margin-min')),
          maximum: percentToRate(value('recipe-margin-max')),
        },
        proposed_prices: value('recipe-proposed')
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        instructions: value('recipe-instructions'),
      }
      await saveRecipe(product.id, content, saved?.revision)
      onSaved()
    })
  }
  function addIngredient() {
    setIngredients([
      ...ingredients,
      {
        key: crypto.randomUUID(),
        label: '',
        quantity: { value: '', unit: 'g' },
        purchase_quantity: { value: '', unit: 'g' },
        purchase_cost: '',
        cost_recorded_on: '',
      },
    ])
    edited()
  }
  return (
    <>
      <ErrorNotice error={action.error} />
      <form onSubmit={save} onChange={edited}>
        <fieldset className="calculator-form" disabled={action.busy}>
          <legend className="sr-only">Private recipe</legend>
          <div className="calculator-grid">
            <Field
              name="recipe-name"
              title="Private recipe name"
              required
              maxLength={200}
              defaultValue={saved?.content.name ?? product.name}
            />
            <Field
              name="recipe-yield"
              title={`Sellable ${product.selling_unit} units per batch`}
              type="number"
              min="1"
              max="1000000"
              step="1"
              required
              defaultValue={saved?.content.sellable_units}
            />
          </div>
          <h3>Raw inputs, not public ingredient claims</h3>
          {ingredients.map((row, index) => (
            <section className="workspace-panel" key={row.key}>
              <h4>Input {index + 1}</h4>
              <div className="calculator-grid">
                <Field
                  name={`recipe-input-label-${row.key}`}
                  title="Input label"
                  required
                  maxLength={200}
                  defaultValue={row.label}
                />
                <Field
                  name={`recipe-input-used-${row.key}`}
                  title="Raw quantity used, including waste"
                  type="number"
                  min="0.000001"
                  max="1000000000"
                  step="0.000001"
                  required
                  defaultValue={row.quantity.value}
                />
                <label className="calculator-field">
                  Used quantity unit
                  <select
                    name={`recipe-input-used-unit-${row.key}`}
                    defaultValue={row.quantity.unit}
                  >
                    {recipeUnits.map((unit) => (
                      <option key={unit}>{unit}</option>
                    ))}
                  </select>
                </label>
                <Field
                  name={`recipe-input-bought-${row.key}`}
                  title="Quantity covered by purchase cost"
                  type="number"
                  min="0.000001"
                  max="1000000000"
                  step="0.000001"
                  required
                  defaultValue={row.purchase_quantity.value}
                />
                <label className="calculator-field">
                  Purchase quantity unit
                  <select
                    name={`recipe-input-bought-unit-${row.key}`}
                    defaultValue={row.purchase_quantity.unit}
                  >
                    {recipeUnits.map((unit) => (
                      <option key={unit}>{unit}</option>
                    ))}
                  </select>
                </label>
                <Field
                  name={`recipe-input-price-${row.key}`}
                  title="Purchase cost (USD)"
                  type="number"
                  min="0"
                  max="1000000000"
                  step="0.000001"
                  required
                  defaultValue={row.purchase_cost}
                />
                <Field
                  name={`recipe-input-date-${row.key}`}
                  title="Cost recorded on"
                  type="date"
                  max={today}
                  required
                  defaultValue={row.cost_recorded_on}
                />
              </div>
              <button
                type="button"
                className="calculator-remove"
                disabled={ingredients.length <= 1}
                onClick={() => {
                  setIngredients(
                    ingredients.filter((item) => item.key !== row.key),
                  )
                  edited()
                }}
              >
                Remove raw input {index + 1}
              </button>
            </section>
          ))}
          <button
            type="button"
            className="calculator-secondary"
            disabled={ingredients.length >= 100}
            onClick={addIngredient}
          >
            Add raw input
          </button>
          <BatchEntries
            prefix="recipe"
            allowMaterials={false}
            initialCosts={saved?.content.other_costs}
            initialLabor={saved?.content.labor}
            onEdit={edited}
          />
          <h3>Your modeled fees and margin targets</h3>
          <div className="calculator-grid">
            <Field
              name="recipe-fee-percent"
              title="Assumed processing rate (%)"
              type="number"
              min="0"
              max="99.9999"
              step="0.0001"
              required
              defaultValue={
                saved
                  ? rateAsPercent(saved.content.payment_fees.rate)
                  : undefined
              }
            />
            <Field
              name="recipe-fee-fixed"
              title="Assumed fixed fee per order (USD)"
              type="number"
              min="0"
              max="1000000000"
              step="0.000001"
              required
              defaultValue={saved?.content.payment_fees.fixed_per_order}
            />
            <Field
              name="recipe-fee-units"
              title="Sellable units sharing one order fee"
              type="number"
              min="1"
              max="1000000"
              step="1"
              required
              defaultValue={saved?.content.payment_fees.units_per_order ?? 1}
            />
            <Field
              name="recipe-margin-min"
              title="Minimum target margin (%)"
              type="number"
              min="0"
              max="99.9999"
              step="0.0001"
              required
              defaultValue={
                saved
                  ? rateAsPercent(saved.content.target_margin.minimum)
                  : undefined
              }
            />
            <Field
              name="recipe-margin-max"
              title="Maximum target margin (%)"
              type="number"
              min="0"
              max="99.9999"
              step="0.0001"
              required
              defaultValue={
                saved
                  ? rateAsPercent(saved.content.target_margin.maximum)
                  : undefined
              }
            />
            <Field
              name="recipe-proposed"
              title="Optional scenario prices USD, comma separated (max 50)"
              maxLength={2000}
              defaultValue={saved?.content.proposed_prices.join(', ')}
            />
          </div>
          <p>
            Enter explicit assumptions, including zero only when intended. These
            are modeled fees and seller targets, not provider-confirmed payment
            fees or a fairness verdict.
          </p>
          <TextArea
            name="recipe-instructions"
            title="Private recipe notes/instructions"
            maxLength={10000}
            defaultValue={saved?.content.instructions}
          />
          <div className="workspace-actions">
            <button
              className="button-primary"
              disabled={Boolean(saved) && !dirty}
            >
              Save private recipe
            </button>
          </div>
        </fieldset>
      </form>
      {saved && (
        <div className="workspace-actions">
          <button
            className="calculator-secondary"
            disabled={dirty || action.busy}
            onClick={() =>
              action.run(async () => {
                costAttempt.current ??= crypto.randomUUID()
                const costing = await createRecipeCosting(
                  product.id,
                  saved.revision,
                  costAttempt.current,
                )
                await onCosted(costing)
                costAttempt.current = null
              })
            }
          >
            Create saved analysis from recipe revision {saved.revision}
          </button>
          {dirty && (
            <p>
              Save recipe edits before creating a costing from this version.
            </p>
          )}
        </div>
      )}
      <p>
        Recipe saves and costings do not consume materials, add sellable stock,
        authorize substitutions or publish recipe inputs. After an uncertain
        request, reload saved history before creating another costing.
      </p>
    </>
  )
}
