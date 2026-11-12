import { useCallback } from 'react'
import type { FormEvent } from 'react'
import { ErrorNotice } from '../../components/Feedback'
import { PrivatePhoto } from '../../components/PrivatePhoto'
import { useResource } from '../../hooks/useResource'
import { useAction } from '../../hooks/useAction'
import { deletePhoto, getPhotos, uploadPhoto } from '../../services/presentation'

export function PresentationStep({ productId }: { productId: string }) {
  const resource = useResource(useCallback((signal) => getPhotos(productId, signal), [productId]))
  const action = useAction()
  function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const file = new FormData(form).get('product-photo')
    void action.run(async () => {
      if (!(file instanceof File)) throw new Error('Choose a JPEG or PNG file.')
      await uploadPhoto(productId, file)
      form.reset()
      resource.reload()
    }, 'Photo uploaded privately. Select it with alt text when you prepare your listing, then approve the new preview.')
  }
  return <section className="workspace-panel"><h2>Let your goods speak for themselves.</h2>
    <p>Upload your own JPEG/PNG, up to 5 MiB. The backend validates and normalizes it. Uploading does not publish the image. Up to 10 photos can be saved per product; select up to 6 for a listing.</p>
    <ErrorNotice error={resource.error || action.error} />
    {action.notice && <p role="status" className="calculator-notice">{action.notice}</p>}
    <form onSubmit={upload}><fieldset className="calculator-form" disabled={action.busy || (resource.data?.items.length ?? 0) >= 10}><legend className="sr-only">Upload private photo</legend>
      <label className="calculator-field">Product photo<input name="product-photo" type="file" accept="image/jpeg,image/png" required /></label>
      <div className="workspace-actions"><button className="button-primary" type="submit">Upload private photo</button></div>
    </fieldset></form>
    {resource.loading && <p role="status">Loading photo library…</p>}
    <div className="workspace-grid">{resource.data?.items.map((photo, index) => <figure className="photo-tile" key={photo.id}>
      <PrivatePhoto productId={productId} photoId={photo.id} alt={`Private product photo ${index + 1}`} /><figcaption>{photo.width} × {photo.height} · {Math.ceil(photo.byte_count / 1024)} KiB</figcaption>
      <button className="calculator-secondary" disabled={action.busy} onClick={() => action.run(async () => { await deletePhoto(productId, photo.id); resource.reload() }, 'Unused private photo deleted.')}>Delete unused photo {index + 1}</button>
    </figure>)}</div>
    {!resource.loading && !resource.data?.items.length && <p>No photos yet. No stock photo will be presented as your product.</p>}
    <p>A photo in a draft or active listing must be removed from those selections before the server permits deletion.</p>
    <button className="calculator-secondary" onClick={resource.reload}>Refresh photos</button>
  </section>
}

export function PhotoSelection({ productId, selected }: { productId: string; selected: { photo_id: string; alt_text: string }[] }) {
  const resource = useResource(useCallback((signal) => getPhotos(productId, signal), [productId]))
  return <section><h3>Choose listing photos</h3><ErrorNotice error={resource.error} />
    <p>Select up to six private photos. Each selected photo needs useful alt text; its actual image is part of the public listing preview.</p>
    {resource.loading && <p role="status">Loading selectable photos…</p>}
    <div className="workspace-grid">{resource.data?.items.map((photo, index) => <div className="photo-tile" key={photo.id}>
      <PrivatePhoto productId={productId} photoId={photo.id} alt={`Private photo option ${index + 1}`} />
      <label className="workspace-check"><input type="checkbox" name="listing-photo" value={photo.id} defaultChecked={selected.some((item) => item.photo_id === photo.id)} />Include photo {index + 1}</label>
      <label className="calculator-field">Photo {index + 1} alt text<input name={`photo-alt-${photo.id}`} maxLength={200} defaultValue={selected.find((item) => item.photo_id === photo.id)?.alt_text ?? ''} /></label>
    </div>)}</div>
    {Boolean(resource.error) && <p>Photo selection could not load. Existing selections are retained; refresh before changing them.</p>}
    <input type="hidden" name="photo-selection-loaded" value={resource.data ? 'yes' : 'no'} />
  </section>
}
