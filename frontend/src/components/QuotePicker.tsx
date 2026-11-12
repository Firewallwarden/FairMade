import { HistorySelection } from './HistorySelection'
import { useCallback, useState } from 'react'
import { getProducts } from '../services/seller'
import { getSourcingInputs, getSupplierQuotes } from '../services/suppliers'
import { useResource } from '../hooks/useResource'
import { ErrorNotice } from './Feedback'
export function QuotePicker({ name }: { name: string }) {
  const [offset, setOffset] = useState(0),
    [product, setProduct] = useState(''),
    [input, setInput] = useState('')
  const products = useResource(
    useCallback((signal) => getProducts(offset, signal), [offset]),
  )
  const inputs = useResource(
    useCallback(
      (signal) =>
        product ? getSourcingInputs(product, signal) : Promise.resolve(null),
      [product],
    ),
  )
  const quotes = useResource(
    useCallback(
      (signal) =>
        product && input
          ? getSupplierQuotes(product, input, signal)
          : Promise.resolve(null),
      [product, input],
    ),
  )
  return (
    <>
      <ErrorNotice error={products.error || inputs.error || quotes.error} />
      {products.data && (
        <label className="calculator-field">
          Quote’s product (20 per page)
          <select
            value={product}
            onChange={(event) => {
              setProduct(event.target.value)
              setInput('')
            }}
          >
            <option value="">Choose product</option>
            {products.data.items.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <div className="workspace-actions">
        <button
          type="button"
          className="calculator-secondary"
          disabled={!offset}
          onClick={() => {
            setProduct('')
            setInput('')
            setOffset(offset - 20)
          }}
        >
          Previous products
        </button>
        <button
          type="button"
          className="calculator-secondary"
          disabled={(products.data?.items.length ?? 0) < 20}
          onClick={() => {
            setProduct('')
            setInput('')
            setOffset(offset + 20)
          }}
        >
          Next products
        </button>
      </div>
      {inputs.data && (
        <HistorySelection productId={product} kind="sourcing-inputs" title="Quoted ingredient/material" value={input} onSelect={setInput} />
      )}
      {quotes.data && (
        <HistorySelection productId={product} kind="supplier-quotes" title="Source quote" key={`${product}-${input}`} inputId={input} name={name} required />
      )}
    </>
  )
}
