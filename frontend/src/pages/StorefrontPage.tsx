import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { ErrorNotice, SignInPrompt } from '../components/Feedback'
import { Field, TextArea } from '../components/FormFields'
import { useAction } from '../hooks/useAction'
import { useResource } from '../hooks/useResource'
import { fieldValue } from '../utils/form'
import { usd } from '../utils/presentation'
import { useSession } from '../services/session'
import {
  browseStorefronts,
  getOwnStorefronts,
  getPublicStorefront,
  getStorefrontListings,
  getStorefrontPreview,
  publishStorefront,
  saveStorefront,
  searchNearbyStorefronts,
  withdrawStorefront,
} from '../services/presentation'

export function StorefrontSettingsPage() {
  const session = useSession()
  return (
    <WorkspaceLayout
      title="A home for your kind of good."
      intro="Create a public storefront without sharing private account details."
    >
      {!session ? (
        <SignInPrompt />
      ) : !session.account.roles.includes('seller') ? (
        <p>
          Seller access is required.{' '}
          <a href="#/account">View application status.</a>
        </p>
      ) : (
        <StorefrontEditor />
      )}
    </WorkspaceLayout>
  )
}

function StorefrontEditor() {
  const resource = useResource(
    useCallback((signal) => getOwnStorefronts(signal), []),
  )
  const [draft, setDraft] = useState<Awaited<
    ReturnType<typeof saveStorefront>
  > | null>(null)
  const [preview, setPreview] = useState<Awaited<
    ReturnType<typeof getStorefrontPreview>
  > | null>(null)
  const action = useAction()
  const current = draft ?? resource.data?.items[0]

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    void action.run(async () => {
      const area = fields.has('store-area-optin')
      const saved = await saveStorefront(
        {
          display_name: fieldValue(fields, 'store-name'),
          description: fieldValue(fields, 'store-description') || null,
          location: fieldValue(fields, 'store-location') || null,
          approximate_area: area
            ? {
                label: fieldValue(fields, 'store-area-label'),
                latitude: fieldValue(fields, 'store-latitude'),
                longitude: fieldValue(fields, 'store-longitude'),
                basis: 'seller_chosen_approximate',
              }
            : null,
        },
        current?.id,
        current?.revision,
      )
      setDraft(saved)
      setPreview(await getStorefrontPreview(saved.id))
    }, 'Draft saved. Review exactly what will become public, then approve it.')
  }

  return (
    <>
      <ErrorNotice error={resource.error || action.error} />
      {action.notice && (
        <p className="calculator-notice" role="status">
          {action.notice}
        </p>
      )}
      {resource.loading && <p role="status">Loading your storefront…</p>}
      {resource.data && (
        <section className="workspace-panel">
          <h2>{current ? 'Your storefront' : 'Meet your neighbors.'}</h2>
          <p>
            One storefront per seller account. Public text and any approximate
            area require explicit publication approval. A draft edit leaves the
            existing approved snapshot unchanged.
          </p>
          {current && (
            <p>
              Current draft state: {current.state}; revision {current.revision}.
            </p>
          )}
          <form
            key={current?.id ?? 'new'}
            onSubmit={save}
            onChange={() => setPreview(null)}
          >
            <fieldset disabled={action.busy} className="calculator-form">
              <legend className="sr-only">Storefront draft</legend>
              <div className="calculator-grid">
                <Field
                  name="store-name"
                  title="Public display name"
                  required
                  maxLength={200}
                  defaultValue={current?.content.display_name}
                />
                <Field
                  name="store-location"
                  title="Public town/area label (optional)"
                  maxLength={200}
                  defaultValue={current?.content.location ?? ''}
                />
                <TextArea
                  name="store-description"
                  title="Public description (optional)"
                  maxLength={2000}
                  defaultValue={current?.content.description ?? ''}
                />
              </div>
              <details>
                <summary>Optional nearby discovery</summary>
                <label className="workspace-check">
                  <input
                    type="checkbox"
                    name="store-area-optin"
                    defaultChecked={Boolean(current?.content.approximate_area)}
                  />
                  Publish a seller-chosen approximate representative point for
                  nearby discovery.
                </label>
                <p>
                  Use an area center you are comfortable making public, not a
                  private pickup address. Coordinates are public if approved; a
                  rounded point does not guarantee anonymity. No map/geocoding
                  service is used.
                </p>
                <div className="calculator-grid">
                  <Field
                    name="store-area-label"
                    title="Approximate area name"
                    maxLength={200}
                    defaultValue={current?.content.approximate_area?.label}
                  />
                  <Field
                    name="store-latitude"
                    title="Public latitude (up to 2 decimals)"
                    type="number"
                    min="-90"
                    max="90"
                    step="0.01"
                    defaultValue={current?.content.approximate_area?.latitude}
                  />
                  <Field
                    name="store-longitude"
                    title="Public longitude (up to 2 decimals)"
                    type="number"
                    min="-180"
                    max="180"
                    step="0.01"
                    defaultValue={current?.content.approximate_area?.longitude}
                  />
                </div>
              </details>
              <div className="workspace-actions">
                <button type="submit" className="button-primary">
                  Save & preview storefront
                </button>
              </div>
            </fieldset>
          </form>
        </section>
      )}
      {preview && current && (
        <section className="workspace-panel">
          <p className="eyebrow">Exact public storefront preview</p>
          <StorefrontContent content={preview.payload} />
          <form
            onSubmit={(event) => {
              event.preventDefault()
              if (!new FormData(event.currentTarget).has('approve-storefront'))
                return
              void action.run(async () => {
                await publishStorefront(
                  current.id,
                  preview.revision,
                  preview.preview_hash,
                )
                setPreview(null)
                setDraft(null)
                resource.reload()
              }, 'Your approved storefront is published.')
            }}
          >
            <label className="workspace-check">
              <input
                key={preview.preview_hash}
                type="checkbox"
                name="approve-storefront"
                required
                disabled={action.busy}
              />
              I approve publishing this exact profile, including any
              representative point shown above.
            </label>
            <div className="workspace-actions">
              <button
                type="submit"
                className="button-primary"
                disabled={action.busy}
              >
                Publish approved storefront
              </button>
            </div>
          </form>
        </section>
      )}
      {current && (
        <div className="workspace-actions">
          <a href={`#/storefront/${current.id}`}>Check public storefront</a>
          {current.state === 'published' && (
            <button
              className="calculator-secondary"
              disabled={action.busy}
              onClick={() =>
                action.run(async () => {
                  await withdrawStorefront(current.id)
                  setPreview(null)
                  setDraft(null)
                  resource.reload()
                }, 'Public storefront withdrawn. Existing order snapshots are unaffected.')
              }
            >
              Withdraw public storefront
            </button>
          )}
        </div>
      )}
      <button
        className="calculator-secondary"
        disabled={action.busy}
        onClick={() => {
          setDraft(null)
          setPreview(null)
          resource.reload()
        }}
      >
        Reload current profile
      </button>
    </>
  )
}

function StorefrontContent({
  content,
}: {
  content: Awaited<ReturnType<typeof getStorefrontPreview>>['payload']
}) {
  return (
    <>
      <h2>{content.display_name}</h2>
      <p>{content.description}</p>
      <p>{content.location ?? 'No public location label.'}</p>
      {content.approximate_area && (
        <p>
          Approximate area: {content.approximate_area.label} ·{' '}
          {content.approximate_area.latitude},{' '}
          {content.approximate_area.longitude} · Seller chosen, unverified.
        </p>
      )}
      <ul>
        {content.notices.map((notice, index) => (
          <li key={index}>{notice}</li>
        ))}
      </ul>
    </>
  )
}

export function StorefrontPage({ id }: { id: string }) {
  const [offset, setOffset] = useState(0)
  const resource = useResource(
    useCallback(
      async (signal) => {
        const [profile, listings] = await Promise.all([
          getPublicStorefront(id, signal),
          getStorefrontListings(id, offset, signal),
        ])
        return { profile, listings }
      },
      [id, offset],
    ),
  )
  return (
    <WorkspaceLayout
      title={resource.data?.profile.payload.display_name ?? 'Meet the maker.'}
    >
      <a href="#/storefronts">← All makers</a>
      <ErrorNotice error={resource.error} />
      {resource.loading && <p role="status">Loading approved storefront…</p>}
      {resource.data && (
        <>
          <section className="workspace-panel">
            <StorefrontContent content={resource.data.profile.payload} />
          </section>
          <h2>Currently approved listings</h2>
          {!resource.data.listings.items.length && (
            <p>No public listings on this page.</p>
          )}
          <div className="workspace-grid">
            {resource.data.listings.items.map((listing) => (
              <article className="workspace-panel" key={listing.id}>
                <h2>{listing.payload.product.title}</h2>
                <p>
                  {usd(listing.payload.price.amount)} /{' '}
                  {listing.payload.product.selling_unit}
                </p>
                <p>{listing.availability.status} · Seller-recorded stock</p>
                <a href={`#/market/${listing.id}`}>View product & Passport</a>
              </article>
            ))}
          </div>
          <div className="workspace-actions">
            <button
              className="calculator-secondary"
              disabled={!offset}
              onClick={() => setOffset(offset - 12)}
            >
              Previous
            </button>
            <button
              className="calculator-secondary"
              disabled={resource.data.listings.items.length < 12}
              onClick={() => setOffset(offset + 12)}
            >
              Next
            </button>
          </div>
        </>
      )}
      <button className="calculator-secondary" onClick={resource.reload}>
        Refresh public profile
      </button>
    </WorkspaceLayout>
  )
}

export function StorefrontDirectoryPage() {
  const [offset, setOffset] = useState(0)
  const [search, setSearch] = useState({
    q: '',
    location: '',
    latitude: '',
    longitude: '',
    radius: '',
  })
  const resource = useResource(
    useCallback(
      async (signal) => {
        if (search.radius)
          return searchNearbyStorefronts(search, offset, signal)
        const result = await browseStorefronts(
          search.q,
          search.location,
          offset,
          signal,
        )
        return {
          ...result,
          items: result.items.map((item) => ({
            ...item,
            distance: null as string | null,
          })),
          notices: [] as string[],
        }
      },
      [search, offset],
    ),
  )
  return (
    <WorkspaceLayout
      title="Meet your neighborhood makers."
      intro="Browse approved profiles or search by an approximate representative point. Distances are estimates, not driving directions or pickup addresses."
    >
      <form
        className="workspace-panel"
        onSubmit={(event) => {
          event.preventDefault()
          const fields = new FormData(event.currentTarget)
          setOffset(0)
          setSearch({
            q: fieldValue(fields, 'maker-q'),
            location: fieldValue(fields, 'maker-location'),
            latitude: fieldValue(fields, 'maker-latitude'),
            longitude: fieldValue(fields, 'maker-longitude'),
            radius: fieldValue(fields, 'maker-radius'),
          })
        }}
      >
        <div className="calculator-grid">
          <Field
            name="maker-q"
            title="Maker name or description"
            maxLength={200}
          />
          <Field
            name="maker-location"
            title="Public location label (all-makers search)"
            maxLength={200}
          />
        </div>
        <details>
          <summary>Nearby search (optional)</summary>
          <p>
            Enter a representative origin and radius together. Coordinates are
            sent in a POST body, not the URL, and are not stored as a buyer
            profile. Clearing radius returns to the all-makers search.
          </p>
          <div className="calculator-grid">
            <Field
              name="maker-latitude"
              title="Origin latitude"
              type="number"
              min="-90"
              max="90"
              step="0.000001"
            />
            <Field
              name="maker-longitude"
              title="Origin longitude"
              type="number"
              min="-180"
              max="180"
              step="0.000001"
            />
            <Field
              name="maker-radius"
              title="Radius (km, 1–500)"
              type="number"
              min="1"
              max="500"
              step="0.1"
            />
          </div>
        </details>
        <div className="workspace-actions">
          <button className="button-primary" type="submit">
            Find makers
          </button>
        </div>
      </form>
      <ErrorNotice error={resource.error} />
      {resource.loading && <p role="status">Finding approved storefronts…</p>}
      {resource.data && (
        <>
          {!resource.data.items.length && (
            <div className="workspace-empty">
              No matching makers on this page. Nearby search only includes
              profiles whose sellers explicitly approved an approximate area.
            </div>
          )}
          <div className="workspace-grid">
            {resource.data.items.map((profile) => (
              <article key={profile.id} className="workspace-panel">
                <h2>{profile.payload.display_name}</h2>
                <p>{profile.payload.description}</p>
                <p>{profile.payload.location}</p>
                {profile.distance !== null && (
                  <p>Estimated distance: {profile.distance} km.</p>
                )}
                <a href={`#/storefront/${profile.id}`}>Meet this maker</a>
              </article>
            ))}
          </div>
          <ul>
            {resource.data.notices.map((notice, index) => (
              <li key={index}>{notice}</li>
            ))}
          </ul>
          <div className="workspace-actions">
            <button
              className="calculator-secondary"
              disabled={!offset}
              onClick={() => setOffset(offset - 12)}
            >
              Previous
            </button>
            <button
              className="calculator-secondary"
              disabled={resource.data.items.length < 12}
              onClick={() => setOffset(offset + 12)}
            >
              Next
            </button>
          </div>
        </>
      )}
      <button className="calculator-secondary" onClick={resource.reload}>
        Refresh makers
      </button>
    </WorkspaceLayout>
  )
}
