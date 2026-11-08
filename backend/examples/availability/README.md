# Synthetic availability workflow

The example uses an existing explicitly activated listing and an approved seller.
$productId and $listingId are its owned private/public UUIDs; $authHeaders is the
seller's bearer-header object. Keep tokens out of files, URLs and Git. Run from
the feature worktree root with its configured environment and migrated database.
The count below is invented development data, not a real availability claim.

```powershell
$api = 'http://127.0.0.1:8000/api/v1'
$inventory = Invoke-RestMethod "$api/products/$productId/inventory" -Headers $authHeaders
$body = @{
    expected_revision = $inventory.revision
    selling_unit = 'loaf'
    on_hand = 10
} | ConvertTo-Json
Invoke-RestMethod "$api/products/$productId/inventory" -Method Put -Headers $authHeaders -ContentType 'application/json' -Body $body
Invoke-RestMethod "$api/marketplace/listings/$listingId"
Invoke-RestMethod "$api/marketplace/listings?availability=available&limit=20&offset=0"
$search = @{
    origin = @{ latitude = '0'; longitude = '0' }
    radius_km = '25'
    availability = 'available'
    limit = 20
} | ConvertTo-Json -Depth 5
Invoke-RestMethod "$api/discovery/listings" -Method Post -ContentType 'application/json' -Body $search
```

With no holds, the public available_units is 10; an active two-loaf hold makes it 8.
Cancelling/expiring an ordinary unpaid hold restores the count; verified payment
consumes stock without double subtraction. Nearby results need a published
storefront with an approved area point covering the illustrative search.

The listing's public selling unit must match inventory for a meaningful number.
Missing or mismatched inventory produces unknown, not a fabricated zero. Exact
counts are an approved product policy, not a temporary MVP limitation. See the
[complete contract](../../../docs/public-listing-availability.md).
