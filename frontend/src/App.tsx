import { useEffect, useState } from 'react'
import { LandingPage } from './pages/LandingPage'
import { PricingPage } from './pages/PricingPage'

export default function App() {
  const [calculator, setCalculator] = useState(window.location.hash === '#/pricing')
  useEffect(() => {
    const navigate = () => setCalculator(window.location.hash === '#/pricing')
    window.addEventListener('hashchange', navigate)
    return () => window.removeEventListener('hashchange', navigate)
  }, [])
  useEffect(() => {
    document.title = calculator ? 'Cost calculator | FairMade' : 'FairMade | A little more local'
    if (calculator) {
      window.scrollTo(0, 0)
      document.getElementById('calculator-main')?.focus({ preventScroll: true })
    }
  }, [calculator])
  return calculator ? <PricingPage /> : <LandingPage />
}
