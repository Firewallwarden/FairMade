import { useCallback, useEffect, useState } from 'react'

// Pass a useCallback loader so requests follow the resource identity, not renders.
export function useResource<T>(loader: (signal: AbortSignal) => Promise<T>) {
  const [version, setVersion] = useState(0)
  const [state, setState] = useState<{
    loader: typeof loader
    version: number
    data?: T
    error?: unknown
  } | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    loader(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setState({ loader, version, data })
      },
      (error) => {
        if (!controller.signal.aborted) setState({ loader, version, error })
      },
    )
    return () => controller.abort()
  }, [loader, version])
  const current = state?.loader === loader && state.version === version
  const reload = useCallback(() => setVersion((value) => value + 1), [])
  return {
    data: current ? state.data : undefined,
    error: current ? state.error : undefined,
    loading: !current,
    reload,
  }
}
