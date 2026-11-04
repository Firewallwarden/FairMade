# Private favorites and saved products

Local development only. Run the backend migrations first. Any authenticated
FairMade account can save products; seller access is not required. These
PowerShell commands assume `$api = 'http://127.0.0.1:8000/api/v1'` and the
account's in-memory `$authHeaders` from the
[account workflow](../seller-workflow.md). Do not log or commit tokens.
See the [favorites API contract](../../../docs/api-contract.md#private-favorites-and-saved-products).

## Save a visible listing

```powershell
$catalog = Invoke-RestMethod -Uri "$api/marketplace/listings?limit=1"
if ($catalog.items.Count -eq 0) { throw 'Create and activate a synthetic listing first.' }
$listing = $catalog.items[0]
$favoritesUrl = "$api/favorites"
$body = @{ listing_id = $listing.id } | ConvertTo-Json
$favorite = Invoke-RestMethod -Method Post -Uri $favoritesUrl -Headers $authHeaders -ContentType 'application/json' -Body $body
Invoke-RestMethod -Method Post -Uri $favoritesUrl -Headers $authHeaders -ContentType 'application/json' -Body $body
```

A first save returns 201; an existing bookmark returns 200 with its original
ID/time. Only the listing's current public visibility is checked. Saving does not
hold its price, reserve inventory or verify quality/availability.

## Read and remove your own saved products

```powershell
$page = Invoke-RestMethod -Uri "$($favoritesUrl)?limit=20&offset=0" -Headers $authHeaders
$page | ConvertTo-Json -Depth 15
Invoke-RestMethod -Uri "$favoritesUrl/$($favorite.id)" -Headers $authHeaders
Invoke-RestMethod -Method Delete -Uri "$favoritesUrl/$($favorite.id)" -Headers $authHeaders
```

Other accounts cannot read or remove this favorite. Authenticated requests only
return the owner's data and use Cache-Control: no-store.

If a listing becomes hidden or its seller loses access, its bookmark remains with
listing_visible=false and listing=null. It retains only the previously known
listing ID and bookmark time, with no copied catalog description/price or private
product data. You can remove it normally. Reactivation/new approved publication
returns the current public card without changing when you saved it.

Migration 0013 follows 0012 and preserves existing data. Downgrade refuses while
favorites or earlier protected history exists. Shared pagination accepts limit
1-100 and nonnegative signed 64-bit offsets. Browser DELETE still requires an approved,
explicit CORS origin. No frontend changes or public favorite counts are included.
