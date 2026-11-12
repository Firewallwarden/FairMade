import { useCallback, useRef } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { ErrorNotice } from '../components/Feedback'
import { useResource } from '../hooks/useResource'
import { useAction } from '../hooks/useAction'
import { useSession } from '../services/session'
import { getCatalogListing } from '../services/commerce'
import { createConversation } from '../services/assistants'
import { usd } from '../utils/presentation'
import { PassportView } from '../components/PassportView'

export function ComparePage({ ids }: { ids: string[] }) {
  const key = ids.join(',')
  const resource = useResource(
    useCallback(
      (signal) =>
        Promise.all(key.split(',').map((id) => getCatalogListing(id, signal))),
      [key],
    ),
  )
  const action = useAction()
  const session = useSession()
  const requestId = useRef(crypto.randomUUID())
  return (
    <WorkspaceLayout
      title="Good choices start with a clearer view."
      intro="Compare currently approved public disclosures. Unknown is not zero, and matching units or claims do not establish equal quality or suitability."
    >
      <a href="#/market">← Choose products at the market</a>
      <ErrorNotice error={resource.error || action.error} />
      {resource.loading && (
        <p role="status">Loading current public Passports…</p>
      )}
      {resource.data && (
        <>
          <section className="workspace-panel">
            <h2>A few goods, side by side.</h2>
            <div
              className="calculator-table-scroll"
              role="region"
              aria-label="Product comparison table"
              tabIndex={0}
            >
              <table className="product-comparison-table">
                <caption>
                  Seller-approved snapshots, fetched now. Prices are USD.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Disclosed information</th>
                    {resource.data.map((listing) => (
                      <th key={listing.id} scope="col">
                        <a href={`#/market/${listing.id}`}>
                          {listing.payload.product.title}
                        </a>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <th scope="row">Maker</th>
                    {resource.data.map((item) => (
                      <td key={item.id}>
                        {item.payload.seller_display_name}
                        <br />
                        {item.payload.location ?? 'Location undisclosed'}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row">Listed selling-unit price</th>
                    {resource.data.map((item) => (
                      <td key={item.id}>
                        <strong>{usd(item.payload.price.amount)}</strong> /{' '}
                        {item.payload.product.selling_unit}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row">Declared quantity</th>
                    {resource.data.map((item) => (
                      <td key={item.id}>
                        {item.payload.selling_quantity
                          ? `${item.payload.selling_quantity.value} ${item.payload.selling_quantity.unit}`
                          : 'Not disclosed'}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row">Backend standard unit price</th>
                    {resource.data.map((item) => (
                      <td key={item.id}>
                        {item.payload.unit_price
                          ? `${item.payload.unit_price.amount === null ? 'Below display precision' : usd(item.payload.unit_price.amount)} per ${item.payload.unit_price.reference_unit}`
                          : 'Unknown; not comparable on a standard-unit basis'}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row">Reported availability</th>
                    {resource.data.map((item) => (
                      <td key={item.id}>
                        {item.availability.status.replaceAll('_', ' ')}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row">Disclosed production cost</th>
                    {resource.data.map((item) => (
                      <td key={item.id}>
                        {item.passport.costs?.unit_cost == null
                          ? 'Not disclosed; not zero'
                          : `${usd(item.passport.costs.unit_cost)} per ${item.passport.product.selling_unit}`}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row">Unverified quality claim check</th>
                    {resource.data.map((item) => (
                      <td key={item.id}>
                        {item.passport.quality_summary?.status.replaceAll(
                          '_',
                          ' ',
                        ) ?? 'Not disclosed'}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row">Passport reviewed</th>
                    {resource.data.map((item) => (
                      <td key={item.id}>{item.passport.reviewed_on}</td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
            <p>
              There is no universal “fairest” or “best quality” winner. Compare
              standard prices only when the product type, reference unit and
              relevant qualities fit your needs.
            </p>
            {session ? (
              <button
                className="calculator-secondary"
                disabled={action.busy}
                onClick={() =>
                  action.run(async () => {
                    const conversation = await createConversation(
                      { role: 'buyer', listing_ids: ids },
                      requestId.current,
                    )
                    window.location.hash = `/assistant/conversations/${conversation.id}`
                  })
                }
              >
                Ask FairMade about these products
              </button>
            ) : (
              <a href="#/account">
                Sign in to ask FairMade about this comparison
              </a>
            )}
          </section>
          {resource.data.map((item) => (
            <details className="workspace-panel" key={item.id}>
              <summary>
                Full approved Passport: {item.payload.product.title}
              </summary>
              <PassportView passport={item.passport} />
            </details>
          ))}
        </>
      )}
      <div className="workspace-actions">
        <button className="calculator-secondary" onClick={resource.reload}>
          Reload current public disclosures
        </button>
      </div>
    </WorkspaceLayout>
  )
}
