# Synthetic inventory and unpaid order workflow

Local development only. Start from the [marketplace workflow](../marketplace/README.md)
and keep the listing active (stop before its deactivation example).
Its seller variables are $api, $authHeaders, $product, and $listing.
Set $buyerHeaders from a different buyer account's normal login response.
Never check real tokens into examples, output, or transcripts.

```powershell
$publicListing = Invoke-RestMethod -Uri "$api/marketplace/listings/$($listing.id)"
$stockUrl = "$api/products/$($product.id)/inventory"
$stock = Invoke-RestMethod -Uri $stockUrl -Headers $authHeaders
$stockBody = @{
    expected_revision = $stock.revision
    selling_unit = $publicListing.payload.product.selling_unit
    on_hand = 20
}
Invoke-RestMethod -Method Put -Uri $stockUrl -Headers $authHeaders `
    -ContentType "application/json" -Body ($stockBody | ConvertTo-Json)

$cart = @{
    items = @(@{
        listing_id = $publicListing.id
        expected_listing_revision = $publicListing.published_revision
        quantity = 2
    })
} | ConvertTo-Json -Depth 10
$preview = Invoke-RestMethod -Method Post -Uri "$api/orders/preview" `
    -Headers $buyerHeaders -ContentType "application/json" -Body $cart
$preview | ConvertTo-Json -Depth 20

$createHeaders = $buyerHeaders.Clone()
$createHeaders["Idempotency-Key"] = [guid]::NewGuid().ToString()
$order = Invoke-RestMethod -Method Post -Uri "$api/orders" `
    -Headers $createHeaders -ContentType "application/json" -Body $cart
# Retry an uncertain result with the SAME key and body; do not reserve twice.
Invoke-RestMethod -Method Post -Uri "$api/orders" -Headers $createHeaders `
    -ContentType "application/json" -Body $cart

Invoke-RestMethod -Uri "$api/orders/$($order.id)" -Headers $buyerHeaders
Invoke-RestMethod -Uri "$api/seller/orders" -Headers $authHeaders
Invoke-RestMethod -Method Post -Uri "$api/orders/$($order.id)/cancel" -Headers $buyerHeaders
```

The preview and saved order show exact merchandise subtotals. They do not confirm
a purchase or payment. Creation holds whole sellable units for 15 minutes.
Cancellation/expiry releases the hold without reducing on-hand stock.

One order contains one seller's products; create separate orders for other sellers.
Inventory basis must match the approved selling unit exactly. No recipe/material
unit conversions, tax/shipping defaults, merchant accounts, or payment success are
inferred. Seller verification is still required to manage stock.
