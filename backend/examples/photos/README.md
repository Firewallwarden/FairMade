# Direct product photo uploads (synthetic local example)

Install the feature backend dependencies, including Pillow 13, and migrate the
isolated development database through 0016. `$headers` is an authenticated verified
seller Authorization header. `$productId` is their existing product with a listing
and approved Passport. `$imagePath` points to a synthetic local JPEG or PNG.
These commands upload/publish only; they never grant seller access or place orders.

```powershell
$base = 'http://127.0.0.1:8000'
$productPath = "$base/api/v1/products/$productId"
# Use image/jpeg for JPEG bytes. Do not send multipart/form-data or JSON/base64.
$photo = Invoke-RestMethod "$productPath/photos" -Method Post -Headers $headers -ContentType 'image/png' -InFile $imagePath
$photo | ConvertTo-Json
$draft = Invoke-RestMethod "$productPath/listing" -Headers $headers
$body = @{
    expected_revision = $draft.revision
    passport_publication_id = $draft.content.passport_publication_id
    seller_display_name = $draft.content.seller_display_name
    location = $draft.content.location
    summary = $draft.content.summary
    photos = @(@{ photo_id = $photo.id; alt_text = 'Synthetic example product photo' })
} | ConvertTo-Json -Depth 6
Invoke-RestMethod "$productPath/listing" -Method Put -Headers $headers -ContentType 'application/json' -Body $body
$preview = Invoke-RestMethod "$productPath/listing/preview" -Headers $headers
$preview.payload | ConvertTo-Json -Depth 8
# Review the selected photos/order/alt text and the rest of the preview first.
$approval = @{
    expected_revision = $preview.revision
    preview_hash = $preview.preview_hash
    approved = $true
} | ConvertTo-Json
Invoke-RestMethod "$productPath/listing/activate" -Method Post -Headers $headers -ContentType 'application/json' -Body $approval
```

Uploads stay private until approved listing activation. Owner preview bytes are
available at `GET /api/v1/products/{product_id}/photos/{photo_id}/content` with the
Authorization header. A frontend should fetch these as authenticated blobs for
private preview; never put the bearer token in an image URL. Anonymous images use
the approved listing photo's relative src path, resolved against the API origin.
These URLs recheck visibility on every read and use no-store, so withdrawal/lost
seller access hides them from subsequent backend reads. Already downloaded images
cannot be recalled from viewers.

Input limit: 5 MiB, JPEG/PNG only, one frame, at most 6000 pixels per side and
16 million pixels. The backend rotates from EXIF orientation, fits to 2048 pixels
per side, flattens transparency onto white, strips metadata and reencodes JPEG.
It stores only normalized bytes and a SHA-256 digest. Up to 10 stored photos per
product and 64 MiB total per seller account; up to six selected photos per listing.
These are explicit local MVP limits, not a media moderation/verification service.

Photo IDs/bytes are immutable. To replace an image, upload a new photo and approve
the new listing selection. Changing a draft leaves the approved image set public
until reactivation or deactivation. Deletion returns PHOTO_IN_USE if the draft or
active listing still references a photo, including an active listing currently
hidden by a withdrawn Passport. Remove it from the draft and either approve the
replacement selection or deactivate the listing before deleting unused content:

```powershell
Invoke-RestMethod "$productPath/photos" -Headers $headers
Invoke-RestMethod "$productPath/photos/$($photo.id)" -Method Delete -Headers $headers
```

Local storage is in SQLite blobs behind the photo repository, so metadata and
bytes save/delete in one transaction. Database backups include images; SQLite may
reuse freed pages instead of shrinking the file. Before hosted use, review managed
media storage, backups/retention, upload/download abuse controls, isolated processing
with hard resource/time limits, dependency updates, and content moderation policy.
No public static upload directory or external image URLs are introduced.
