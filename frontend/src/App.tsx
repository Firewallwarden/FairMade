import { useEffect, useState } from 'react'
import { LandingPage } from './pages/LandingPage'
import { PricingPage } from './pages/PricingPage'
import { AccountPage } from './pages/AccountPage'
import { useSession } from './services/session'
import { SellerPage } from './pages/SellerPage'
import { SellerProductPage } from './pages/SellerProductPage'
import { MarketPage } from './pages/MarketPage'
import { ListingPage } from './pages/ListingPage'
import { OrdersPage } from './pages/OrdersPage'
import { OrderPage } from './pages/OrderPage'
import { WorkspaceLayout } from './components/WorkspaceLayout'
import { AssistantPage } from './pages/AssistantPage'
import { FavoritesPage } from './pages/FavoritesPage'
import { MyReviewsPage } from './pages/MyReviewsPage'
import { ReceiptsPage } from './pages/ReceiptsPage'
import { PreferencesPage } from './pages/PreferencesPage'
import { ShoppingPlanPage } from './pages/ShoppingPlanPage'
import { ComparePage } from './pages/ComparePage'
import { SupplierRecordsPage } from './pages/SupplierRecordsPage'
import {
  StorefrontDirectoryPage,
  StorefrontPage,
  StorefrontSettingsPage,
} from './pages/StorefrontPage'

export default function App() {
  const session = useSession()
  const [route, setRoute] = useState(window.location.hash)
  const calculator = route === '#/pricing'
  useEffect(() => {
    const navigate = () => setRoute(window.location.hash)
    window.addEventListener('hashchange', navigate)
    return () => window.removeEventListener('hashchange', navigate)
  }, [])
  useEffect(() => {
    const section = route.split('/')[1]
    const titles: Record<string, string> = {
      pricing: 'Cost calculator',
      account: 'Your account',
      seller: 'Seller workspace',
      market: 'The market',
      orders: 'Your orders',
      'seller-orders': 'Your orders',
      assistant: 'Ask FairMade',
      favorites: 'Saved goods',
      reviews: 'My reviews',
      receipts: 'Receipts and expenses',
      preferences: 'Buyer preferences',
      planning: 'Shopping plans',
      compare: 'Compare products',
      suppliers: 'Private supplier records',
      storefronts: 'Meet the makers',
      storefront: 'Maker storefront',
    }
    const title = titles[section] ?? 'A little more local'
    document.title = `${title} | FairMade`
    if (calculator) {
      window.scrollTo(0, 0)
      document.getElementById('calculator-main')?.focus({ preventScroll: true })
    }
    if (route.startsWith('#/') && !calculator) {
      window.scrollTo(0, 0)
      document.getElementById('workspace-main')?.focus({ preventScroll: true })
    }
    if (!route.startsWith('#/')) {
      const target = route.startsWith('#') ? route.slice(1) : 'home'
      document.getElementById(target)?.scrollIntoView()
    }
  }, [calculator, route, session?.account.id])
  if (calculator) return <PricingPage />
  if (route === '#/suppliers')
    return <SupplierRecordsPage key={session?.account.id ?? 'guest'} />
  const supplierId = route.match(/^#\/suppliers\/([a-f0-9-]{36})$/i)?.[1]
  if (supplierId)
    return (
      <SupplierRecordsPage
        key={`${session?.account.id}-${supplierId}`}
        id={supplierId}
      />
    )
  const compareRoute = route.match(/^#\/compare\/([a-f0-9,-]+)$/i)?.[1]
  if (compareRoute) {
    const ids = compareRoute.split(',')
    if (
      ids.length >= 2 &&
      ids.length <= 4 &&
      new Set(ids).size === ids.length &&
      ids.every((id) => /^[a-f0-9-]{36}$/i.test(id))
    )
      return (
        <ComparePage key={`${session?.account.id}-${compareRoute}`} ids={ids} />
      )
  }
  if (route === '#/planning') return <ShoppingPlanPage />
  const planRoute = route.match(/^#\/planning\/([a-f0-9-]{36})(\/seller)?$/i)
  if (planRoute)
    return (
      <ShoppingPlanPage
        key={`${session?.account.id}-${route}`}
        storefrontId={planRoute[1]}
        seller={Boolean(planRoute[2])}
      />
    )
  if (route === '#/preferences')
    return <PreferencesPage key={session?.account.id ?? 'guest'} />
  if (route === '#/receipts')
    return <ReceiptsPage key={session?.account.id ?? 'guest'} />
  const receiptId = route.match(/^#\/receipts\/([a-f0-9-]{36})$/i)?.[1]
  if (receiptId)
    return (
      <ReceiptsPage
        key={`${session?.account.id}-${receiptId}`}
        id={receiptId}
      />
    )
  if (route === '#/reviews')
    return <MyReviewsPage key={session?.account.id ?? 'guest'} />
  if (route === '#/favorites')
    return <FavoritesPage key={session?.account.id ?? 'guest'} />
  if (route === '#/storefront/settings')
    return <StorefrontSettingsPage key={session?.account.id ?? 'guest'} />
  if (route === '#/storefronts') return <StorefrontDirectoryPage />
  const storefrontId = route.match(/^#\/storefront\/([a-f0-9-]{36})$/i)?.[1]
  if (storefrontId)
    return <StorefrontPage key={storefrontId} id={storefrontId} />
  const assistantSource = route.match(
    /^#\/assistant\/(buyer|seller)\/([a-f0-9-]{36})$/i,
  )
  if (assistantSource)
    return (
      <AssistantPage
        key={`${session?.account.id}-${route}`}
        source={{
          role: assistantSource[1] === 'seller' ? 'seller' : 'buyer',
          id: assistantSource[2],
        }}
      />
    )
  const conversationId = route.match(
    /^#\/assistant\/conversations\/([a-f0-9-]{36})$/i,
  )?.[1]
  if (conversationId)
    return (
      <AssistantPage
        key={`${session?.account.id}-${conversationId}`}
        id={conversationId}
      />
    )
  if (route === '#/assistant')
    return <AssistantPage key={session?.account.id ?? 'guest'} />
  if (route === '#/account')
    return <AccountPage key={session?.account.id ?? 'guest'} />
  if (route === '#/seller')
    return <SellerPage key={session?.account.id ?? 'guest'} />
  const productId = route.match(/^#\/seller\/([a-f0-9-]{36})$/i)?.[1]
  if (productId)
    return (
      <SellerProductPage
        key={`${session?.account.id}-${productId}`}
        id={productId}
      />
    )
  if (route === '#/market') return <MarketPage />
  const listingId = route.match(/^#\/market\/([a-f0-9-]{36})$/i)?.[1]
  if (listingId)
    return (
      <ListingPage key={`${session?.account.id}-${listingId}`} id={listingId} />
    )
  if (route === '#/orders')
    return <OrdersPage key={session?.account.id ?? 'guest'} />
  const order = route.match(/^#\/(orders|seller-orders)\/([a-f0-9-]{36})$/i)
  if (order)
    return (
      <OrderPage
        key={`${session?.account.id}-${route}`}
        id={order[2]}
        seller={order[1] === 'seller-orders'}
      />
    )
  if (route.startsWith('#/'))
    return (
      <WorkspaceLayout title="This path needs a little care.">
        <p>
          This page does not exist. <a href="#/market">Visit the market.</a>
        </p>
      </WorkspaceLayout>
    )
  return <LandingPage />
}
