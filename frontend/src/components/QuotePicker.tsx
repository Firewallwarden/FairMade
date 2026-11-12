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
        <label className="calculator-field">
          Quoted ingredient/material
          <select
            value={input}
            onChange={(event) => setInput(event.target.value)}
          >
            <option value="">Choose sourcing input</option>
            {inputs.data.items.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
      )}
      {quotes.data && (
        <label className="calculator-field">
          Source quote (latest 100)
          <select name={name} key={input} required>
            <option value="">Choose quote</option>
            {quotes.data.items.map((item) => (
              <option key={item.id} value={item.id}>
                {item.supplier_name} · {item.observed_on} · {item.source.name}
              </option>
            ))}
          </select>
        </label>
      )}
    </>
  )
}
