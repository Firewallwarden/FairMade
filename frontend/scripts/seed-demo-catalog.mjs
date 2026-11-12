import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

// Explicit opt-in; use only the pre-existing approved, synthetic local seller.
// Never bootstrap administrator access, clear records or embed credentials.
const root = fileURLToPath(new URL('../', import.meta.url))
const base = new URL(
  process.env.FAIRMADE_DEMO_API ?? 'http://127.0.0.1:8001/api/v1',
)
const email = process.env.FAIRMADE_DEMO_EMAIL ?? ''
const password = process.env.FAIRMADE_DEMO_PASSWORD ?? ''
if (
  process.env.FAIRMADE_DEMO_SEED !== 'true' ||
  base.protocol !== 'http:' ||
  !['127.0.0.1', 'localhost'].includes(base.hostname) ||
  base.pathname !== '/api/v1' ||
  base.search ||
  base.hash ||
  base.username ||
  base.password ||
  !/^qa-seller-[a-f0-9-]+@example\.com$/.test(email) ||
  !password
) {
  throw new Error(
    'Requires explicit FAIRMADE_DEMO_SEED=true, a loopback /api/v1 API and synthetic QA seller credentials in the process environment.',
  )
}

const catalog = JSON.parse(
  await readFile(join(root, 'demo/catalog.json'), 'utf8'),
)
const statePath = join(root, 'node_modules/.tmp/demo-catalog-state.json')
let token
async function request(method, path, body, raw) {
  const headers = { Accept: 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  if (raw) headers['Content-Type'] = 'image/jpeg'
  else if (body !== undefined) headers['Content-Type'] = 'application/json'
  const response = await fetch(base.href + path, {
    method,
    headers,
    body: raw ?? (body === undefined ? undefined : JSON.stringify(body)),
    signal: AbortSignal.timeout(30000),
    redirect: 'error',
  })
  // Do not print credential payloads or arbitrary validation response bodies.
  if (!response.ok)
    throw new Error(
      `${method} ${path}: HTTP ${response.status}. Existing records were retained; inspect and rerun after resolving the error.`,
    )
  return response.status === 204 ? null : response.json()
}
const login = await request('POST', '/auth/login', { email, password })
token = login.access_token
try {
  const account = await request('GET', '/auth/me')
  if (account.email !== email || !account.roles.includes('seller'))
    throw new Error('An approved synthetic seller is required.')
  let state
  try {
    state = JSON.parse(await readFile(statePath, 'utf8'))
  } catch (error) {
    if (error.code !== 'ENOENT') throw error
    state = { api: base.href, seller: account.id, items: {} }
  }
  if (state.api !== base.href || state.seller !== account.id)
    throw new Error(
      'Saved seed state belongs to another API/account. Existing records were retained.',
    )
  async function save() {
    await mkdir(join(root, 'node_modules/.tmp'), { recursive: true })
    await writeFile(statePath, JSON.stringify(state, null, 2))
  }
  const products = []
  for (let offset = 0; offset < 1000; offset += 100) {
    const page = await request('GET', `/products?limit=100&offset=${offset}`)
    products.push(...page.items)
    if (page.items.length < 100) break
    if (offset === 900)
      throw new Error('Account exceeds bounded demo scan; no products created.')
  }
  for (const item of catalog) {
    const record = (state.items[item.key] ??= {})
    if (record.active) {
      console.log(`Retained: ${item.name}`)
      continue
    }
    const marker = `fairmade-demo-catalog-v1/${item.key}`
    if (!record.product) {
      const existing = products.find((product) =>
        product.description?.includes(marker),
      )
      const product =
        existing ??
        (await request('POST', '/products', {
          name: item.name + ' (Demo)',
          product_type: item.product_type,
          selling_unit: item.selling_unit,
          description: `Fictional demo product. Sample inputs, prices and stock are not real seller claims. [${marker}]`,
        }))
      record.product = product.id
      await save()
    }
    const productPath = `/products/${record.product}`
    if (!record.analysis) {
      const analysis = await request('POST', productPath + '/analyses', {
        currency: 'USD',
        sellable_units: 10,
        costs: [
          {
            label: 'Fictional demo materials',
            category: 'materials',
            amount: item.materials,
          },
          {
            label: 'Fictional demo packaging',
            category: 'packaging',
            amount: item.packaging,
          },
          {
            label: 'Fictional demo overhead',
            category: 'overhead',
            amount: item.overhead,
          },
        ],
        labor: [
          {
            label: 'Fictional demo batch labor',
            hours: item.hours,
            hourly_rate: item.hourly_rate,
          },
        ],
        payment_fees: {
          rate: '0.03',
          fixed_per_order: '0.50',
          units_per_order: 1,
        },
        target_margin: { minimum: '0.20', maximum: '0.35' },
        proposed_prices: [item.price],
      })
      record.analysis = analysis.id
      await save()
    }
    if (!record.review) {
      const review = await request('POST', productPath + '/pricing-reviews', {
        pricing_analysis_id: record.analysis,
      })
      record.review = review.id
      await save()
    }
    if (!record.passport) {
      const draft = await request('POST', productPath + '/passports', {
        review_id: record.review,
        title: item.name + ' (Demo)',
        price: item.price,
        public_description: `Demo listing. ${item.description} All costs, prices, maker names and stock are fictional examples for sandbox testing. Not an offer of real goods. Images, where present, are illustrative.`,
        disclosures: {
          cost_categories: ['materials', 'packaging', 'overhead'],
          include_labor: true,
          include_unit_cost: true,
        },
      })
      record.passport = draft.id
      await save()
    }
    if (!record.publication) {
      const preview = await request(
        'GET',
        productPath + `/passports/${record.passport}/preview`,
      )
      const publication = await request(
        'POST',
        productPath + `/passports/${record.passport}/publish`,
        {
          expected_revision: preview.revision,
          preview_hash: preview.preview_hash,
          approved: true,
        },
      )
      record.publication = publication.id
      await save()
    }
    if (item.image && !record.photo) {
      const bytes = await readFile(join(root, 'public/images', item.image))
      const photo = await request(
        'POST',
        productPath + '/photos',
        undefined,
        bytes,
      )
      record.photo = photo.id
      await save()
    }
    if (!record.listing) {
      const listing = await request('POST', productPath + '/listing', {
        passport_publication_id: record.publication,
        seller_display_name: item.maker + ' (Demo)',
        location: 'Exampletown (demo)',
        summary: `Demo listing. ${item.description} Fictional price and stock; not a real offer.`,
        selling_quantity: item.selling_quantity,
        photos: record.photo
          ? [
              {
                photo_id: record.photo,
                alt_text: `Illustrative demo image for ${item.name}; not a photo of actual goods for sale.`,
              },
            ]
          : [],
      })
      record.listing = listing.id
      await save()
    }
    if (!record.stock) {
      const inventory = await request('GET', productPath + '/inventory')
      await request('PUT', productPath + '/inventory', {
        expected_revision: inventory.revision,
        selling_unit: item.selling_unit,
        on_hand: item.on_hand,
      })
      record.stock = true
      await save()
    }
    const preview = await request('GET', productPath + '/listing/preview')
    await request('POST', productPath + '/listing/activate', {
      expected_revision: preview.revision,
      preview_hash: preview.preview_hash,
      approved: true,
    })
    record.active = true
    await save()
    console.log(`Published demo: ${item.name}`)
  }
  console.log(
    `Demo catalog complete: ${catalog.length} listings. No orders or payments were created.`,
  )
} finally {
  await request('POST', '/auth/logout').catch(() => {})
  token = undefined
}
