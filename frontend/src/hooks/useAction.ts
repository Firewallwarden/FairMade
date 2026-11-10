import { useState } from 'react'

export function useAction() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [notice, setNotice] = useState('')
  async function run(operation: () => Promise<void>, success = '') {
    if (busy) return
    setBusy(true)
    setError(null)
    setNotice('')
    try {
      await operation()
      setNotice(success)
    } catch (error) {
      setError(error)
    } finally {
      setBusy(false)
    }
  }
  return { busy, error, notice, run }
}
