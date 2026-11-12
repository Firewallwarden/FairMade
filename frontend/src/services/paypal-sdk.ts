type ButtonOptions = {
  createOrder: () => Promise<string>
  onApprove: () => Promise<void>
  onCancel: () => void
  onError: (error: unknown) => void
  style: { layout: 'vertical'; label: 'paypal'; shape: 'pill' }
}
type PayPalButtons = {
  render: (container: HTMLElement) => Promise<void>
  close: () => Promise<void>
  isEligible: () => boolean
}
type PayPalSdk = { Buttons: (options: ButtonOptions) => PayPalButtons }

declare global {
  interface Window {
    fairmadePayPal?: PayPalSdk
  }
}

let loading: { clientId: string; promise: Promise<PayPalSdk> } | undefined

// Use PayPal's documented Buttons SDK. Only the backend's public sandbox ID is used.
export function loadPayPal(clientId: string): Promise<PayPalSdk> {
  if (loading) {
    if (loading.clientId !== clientId)
      return Promise.reject(
        new Error(
          'PayPal configuration changed. Reload this page before checkout.',
        ),
      )
    return loading.promise
  }
  const promise = new Promise<PayPalSdk>((resolve, reject) => {
    const script = document.createElement('script')
    const params = new URLSearchParams({
      'client-id': clientId,
      currency: 'USD',
      intent: 'capture',
      components: 'buttons',
      'disable-funding': 'credit,paylater,card,venmo',
    })
    script.src = `https://www.paypal.com/sdk/js?${params}`
    script.dataset.namespace = 'fairmadePayPal'
    script.async = true
    const timer = window.setTimeout(() => fail(), 20000)
    function fail() {
      window.clearTimeout(timer)
      script.remove()
      loading = undefined
      reject(
        new Error(
          'The PayPal sandbox interface could not load. Check your connection or blocker settings and retry.',
        ),
      )
    }
    script.onerror = fail
    script.onload = () => {
      window.clearTimeout(timer)
      if (window.fairmadePayPal) resolve(window.fairmadePayPal)
      else fail()
    }
    document.head.append(script)
  })
  loading = { clientId, promise }
  return promise
}
