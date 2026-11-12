import { useState } from 'react'
import type { FormEvent } from 'react'
import { Field, TextArea } from '../../components/FormFields'
import { ErrorNotice } from '../../components/Feedback'
import { useAction } from '../../hooks/useAction'
import { getPassportDraft, updatePassportDraft } from '../../services/seller'
import type { decodeEditablePassport } from '../../services/passport-contract'
import { costCategories } from '../../types/pricing'
import { fieldValue } from '../../utils/form'

type Draft = ReturnType<typeof decodeEditablePassport>

export function PassportEditor({ productId, draft, onEdit, onSaved }: {
  productId: string
  draft: Draft
  onEdit: () => void
  onSaved: (draft: Draft) => void
}) {
  const action = useAction()
  const [current, setCurrent] = useState(draft)
  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    onEdit()
    void action.run(async () => {
      const saved = await updatePassportDraft(productId, current.id, current.revision, {
        ...current.content,
        title: fieldValue(fields, 'edit-title'),
        price: fieldValue(fields, 'edit-price'),
        public_description: fieldValue(fields, 'edit-description') || null,
        disclosures: {
          ...current.content.disclosures,
          ...Object.fromEntries(Object.keys(current.content.disclosures)
            .filter(key => key !== 'cost_categories').map(key => [key, fields.has(key)])),
          cost_categories: costCategories.filter(category => fields.getAll('edit-category').includes(category)),
        },
      })
      setCurrent(saved)
      onSaved(saved)
    }, 'Draft saved. Generate and review a fresh preview before publication.')
  }
  return <section className="workspace-panel">
    <h3>Edit saved Passport draft</h3>
    <p>Revision {current.revision}. Changes affect only this private draft. The saved review and composition declaration are preserved.</p>
    <ErrorNotice error={action.error} />
    {action.notice && <p role="status">{action.notice}</p>}
    <form key={`${current.id}-${current.revision}`} onSubmit={save} onChange={onEdit}>
      <fieldset disabled={action.busy} className="calculator-form">
        <legend className="sr-only">Saved Passport content and disclosures</legend>
        <Field name="edit-title" title="Passport title" required maxLength={200} defaultValue={current.content.title} />
        <Field name="edit-price" title="Public price (USD)" required type="number" min="0.01" max="1000000000" step="0.01" defaultValue={current.content.price} />
        <TextArea name="edit-description" title="Public description" maxLength={2000} defaultValue={current.content.public_description ?? ''} />
        {Object.entries(current.content.disclosures).filter(([key]) => key !== 'cost_categories').map(([key, value]) => <label className="workspace-check" key={key}>
          <input type="checkbox" name={key} defaultChecked={value === true} disabled={key === 'include_composition' && !current.content.composition} />
          {key.replace('include_', 'Disclose ').replaceAll('_', ' ')}
        </label>)}
        {costCategories.map(category => <label className="workspace-check" key={category}>
          <input type="checkbox" name="edit-category" value={category} defaultChecked={current.content.disclosures.cost_categories.includes(category)} />
          Disclose {category} cost
        </label>)}
        <button type="submit" className="button-primary">Save Passport changes</button>
      </fieldset>
    </form>
    <button className="calculator-secondary" disabled={action.busy} onClick={() => {
      onEdit()
      void action.run(async () => {
        const fresh = await getPassportDraft(productId, current.id)
        setCurrent(fresh)
        onSaved(fresh)
      }, 'Reloaded the saved draft. Unsaved changes were discarded.')
    }}>Reload saved draft after a conflict</button>
  </section>
}
