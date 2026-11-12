import { useCallback, useState } from 'react'
import { getHistoryPage } from '../services/history'
import type { HistoryKind } from '../services/history'
import { useResource } from '../hooks/useResource'
import { ErrorNotice } from './Feedback'

export function HistorySelection({ productId, kind, inputId, name, title, multiple = false, required = false, value, onSelect, initialValue = '', disabled = false }: {
  productId: string; kind: HistoryKind; inputId?: string; name?: string; title: string;
  multiple?: boolean; required?: boolean; value?: string; initialValue?: string; onSelect?: (id: string) => void
  disabled?: boolean
}) {
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<Record<string, string>>(initialValue ? { [initialValue]: initialValue } : {})
  const resource = useResource(useCallback(signal => getHistoryPage(productId, kind, offset, inputId, signal), [productId, kind, offset, inputId]))
  const single = value ?? Object.keys(selected)[0] ?? ''
  const items = resource.data?.items ?? []
  function choose(id: string, label: string) {
    setSelected(id ? { [id]: label } : {})
    onSelect?.(id)
  }
  return <fieldset className="workspace-panel" disabled={disabled}>
    <legend>{title}</legend>
    <ErrorNotice error={resource.error} />
    {resource.loading && <p role="status">Loading {title.toLowerCase()}…</p>}
    {resource.data && !items.length && <p>No records on this page.</p>}
    {multiple ? <>
      <p>{Object.keys(selected).length}/100 selected. Selections are retained when moving between pages.</p>
      {Object.entries(selected).map(([id, label]) => <label key={id} className="workspace-check">
        <input type="hidden" name={name} value={id} />
        <input type="checkbox" checked onChange={() => setSelected(Object.fromEntries(Object.entries(selected).filter(([key]) => key !== id)))} />{label}
      </label>)}
      {items.filter(item => !selected[item.id]).map(item => <label className="workspace-check" key={item.id}>
        <input type="checkbox" checked={false} disabled={Object.keys(selected).length >= 100} onChange={() => setSelected({ ...selected, [item.id]: item.label })} />{item.label}
      </label>)}
    </> : <>
      <input type="hidden" name={name} value={single} />
      <label className="calculator-field">{title}
        <select required={required} value={single} onChange={event => choose(event.target.value, items.find(item => item.id === event.target.value)?.label ?? event.target.value)}>
          <option value="">Choose a record / no selection</option>
          {single && !items.some(item => item.id === single) && <option value={single}>{selected[single] ?? single} (selected from another page)</option>}
          {items.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
      </label>
    </>}
    <div className="workspace-actions">
      <button type="button" className="calculator-secondary" disabled={resource.loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous {title.toLowerCase()}</button>
      <span>Page {offset / 20 + 1}</span>
      <button type="button" className="calculator-secondary" disabled={resource.loading || !resource.data || items.length < 20} onClick={() => setOffset(offset + 20)}>Next {title.toLowerCase()}</button>
      <button type="button" className="calculator-secondary" disabled={resource.loading} onClick={resource.reload}>Refresh {title.toLowerCase()}</button>
    </div>
  </fieldset>
}
