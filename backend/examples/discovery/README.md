# Approximate-area discovery (synthetic local examples)

Use the migrated feature backend (`alembic upgrade head`, through 0015) at
http://127.0.0.1:8000. `$headers` holds a verified seller's bearer Authorization
header; `$storefrontId` is their existing storefront UUID. Examples never grant
roles. Coordinates below are synthetic; do not use a private address. No external
maps/geocoding calls occur, and these requests do not place orders.

Replace the current draft, preview it, then explicitly approve the exact payload.
PUT replaces all optional fields, so retain desired descriptions/location labels.

```powershell
$base = 'http://127.0.0.1:8000'
$path = "$base/api/v1/seller/storefronts/$storefrontId"
$current = Invoke-RestMethod $path -Headers $headers
$body = @{
    expected_revision = $current.revision
    display_name = 'Synthetic example bakery'
    location = 'Synthetic example town'
    approximate_area = @{
        label = 'Synthetic example town area'
        latitude = '40.00'
        longitude = '-90.00'
    }
} | ConvertTo-Json -Depth 5
Invoke-RestMethod $path -Method Put -Headers $headers -ContentType 'application/json' -Body $body
$preview = Invoke-RestMethod "$path/preview" -Headers $headers
$preview.payload | ConvertTo-Json -Depth 8
# Review the public point and notices before approving this exact preview.
$approval = @{
    expected_revision = $preview.revision
    preview_hash = $preview.preview_hash
    approved = $true
} | ConvertTo-Json
Invoke-RestMethod "$path/publish" -Method Post -Headers $headers -ContentType 'application/json' -Body $approval
```

Anonymous searches are read-only POSTs. The backend does not save/echo the buyer
origin. Avoid recording request bodies in browser/server logs. Coordinates belong
in the body, not query parameters. Distances estimate straight-line distance to
seller-chosen area points; no pickup/delivery or stock guarantee is made.

```powershell
$body = @{
    origin = @{ latitude = '40.00'; longitude = '-90.00' }
    radius_km = '25.0'
    limit = 20
    offset = 0
} | ConvertTo-Json -Depth 5
Invoke-RestMethod "$base/api/v1/discovery/storefronts" -Method Post -ContentType 'application/json' -Body $body
Invoke-RestMethod "$base/api/v1/discovery/listings" -Method Post -ContentType 'application/json' -Body $body
```

Pages return items, limit, offset, distance_basis and notices. Storefront items
contain storefront and estimated_distance_km; listing items contain listing,
storefront_id, approximate_area and estimated_distance_km. Estimates are strings
such as "1.1". Optional q filters approved text; listing search also accepts
product_type. Seller access and publication visibility are rechecked on each
query. Existing profiles without an approved point do not match nearby search.

To remove a point, replace the draft with approximate_area=null (or omit it),
then preview and approve again. Draft removal alone leaves the approved point
public. Withdrawing a storefront hides its nearby results immediately while
independent regular catalog listings remain governed by their own approvals.

Use a smaller radius or more specific q/product_type when 409 SEARCH_TOO_BROAD
indicates more than 1,000 bounding-box candidates. This is an explicit local MVP
limit; no truncated nearest-first list is returned. Precise locations, geocoding,
route planning and scaled spatial search require later review.
