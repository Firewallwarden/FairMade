import { useEffect, useState } from 'react'
import { getPhotoContent } from '../services/presentation'

export function PrivatePhoto({ productId, photoId, alt }: { productId: string; photoId: string; alt: string }) {
  const [state, setState] = useState<{ url?: string; error?: string }>({})
  useEffect(() => {
    const controller = new AbortController()
    let url: string | undefined
    getPhotoContent(productId, photoId, controller.signal).then((blob) => {
      if (controller.signal.aborted) return
      url = URL.createObjectURL(blob)
      setState({ url })
    }).catch(() => { if (!controller.signal.aborted) setState({ error: 'Image unavailable. Refresh photos to check access.' }) })
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url) }
  }, [productId, photoId])
  return state.url ? <img className="private-photo" src={state.url} alt={alt} /> : <p role="status">{state.error ?? 'Loading private photo…'}</p>
}
