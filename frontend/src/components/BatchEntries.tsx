import { useState } from 'react'
import { Field } from './FormFields'
import { costCategories } from '../types/pricing'
import type { BatchCost, LaborCost } from '../types/pricing'
export function BatchEntries({
  prefix,
  initialCosts = [],
  initialLabor = [],
  allowMaterials = true,
  costLimit = 100,
  onEdit,
}: {
  prefix: string
  initialCosts?: BatchCost[]
  initialLabor?: LaborCost[]
  allowMaterials?: boolean
  costLimit?: number
  onEdit?: () => void
}) {
  const [costs, setCosts] = useState(() =>
    initialCosts.map((cost) => ({ ...cost, key: crypto.randomUUID() })),
  )
  const [labor, setLabor] = useState(() =>
    initialLabor.map((row) => ({ ...row, key: crypto.randomUUID() })),
  )
  const categories = costCategories.filter(
    (category) => allowMaterials || category !== 'materials',
  )
  return (
    <>
      <h3>{allowMaterials ? 'Recorded batch costs' : 'Other batch costs'}</h3>
      <p>
        Enter whole-batch allocations. Unentered costs are excluded from the
        model; that does not establish zero actual spending.
      </p>
      {costs.map((row, index) => (
        <div className="calculator-grid" key={row.key}>
          <input type="hidden" name={`${prefix}-cost-row`} value={row.key} />
          <Field
            name={`${prefix}-cost-label-${row.key}`}
            title={`Cost ${index + 1} label`}
            required
            maxLength={200}
            defaultValue={row.label}
          />
          <label className="calculator-field">
            Cost category
            <select
              name={`${prefix}-cost-category-${row.key}`}
              defaultValue={row.category}
            >
              {categories.map((category) => (
                <option key={category}>{category}</option>
              ))}
            </select>
          </label>
          <Field
            name={`${prefix}-cost-amount-${row.key}`}
            title="Whole-batch amount (USD)"
            type="number"
            min="0"
            max="1000000000"
            step="0.000001"
            required
            defaultValue={row.amount}
          />
          <button
            className="calculator-remove"
            type="button"
            onClick={() => {
              setCosts(costs.filter((item) => item.key !== row.key))
              onEdit?.()
            }}
          >
            Remove cost {index + 1}
          </button>
        </div>
      ))}
      <button
        className="calculator-secondary"
        type="button"
        disabled={costs.length >= costLimit}
        onClick={() => {
          setCosts([
            ...costs,
            {
              key: crypto.randomUUID(),
              label: '',
              category: categories[0],
              amount: '',
            },
          ])
          onEdit?.()
        }}
      >
        Add batch cost
      </button>
      <h3>Recorded batch labor</h3>
      {labor.map((row, index) => (
        <div className="calculator-grid" key={row.key}>
          <input type="hidden" name={`${prefix}-labor-row`} value={row.key} />
          <Field
            name={`${prefix}-labor-label-${row.key}`}
            title={`Labor ${index + 1} label`}
            required
            maxLength={200}
            defaultValue={row.label}
          />
          <Field
            name={`${prefix}-labor-hours-${row.key}`}
            title="Batch labor hours"
            type="number"
            min="0"
            max="1000000000"
            step="0.000001"
            required
            defaultValue={row.hours}
          />
          <Field
            name={`${prefix}-labor-rate-${row.key}`}
            title="Hourly rate (USD)"
            type="number"
            min="0"
            max="1000000000"
            step="0.000001"
            required
            defaultValue={row.hourly_rate}
          />
          <button
            className="calculator-remove"
            type="button"
            onClick={() => {
              setLabor(labor.filter((item) => item.key !== row.key))
              onEdit?.()
            }}
          >
            Remove labor {index + 1}
          </button>
        </div>
      ))}
      <button
        className="calculator-secondary"
        type="button"
        disabled={labor.length >= 100}
        onClick={() => {
          setLabor([
            ...labor,
            { key: crypto.randomUUID(), label: '', hours: '', hourly_rate: '' },
          ])
          onEdit?.()
        }}
      >
        Add batch labor
      </button>
    </>
  )
}
