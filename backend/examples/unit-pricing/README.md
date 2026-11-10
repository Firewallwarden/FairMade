# Synthetic standardized quantity and unit price

Run the [backend setup](../../README.md) and use an existing synthetic sourdough
product with an approved Passport and listing draft, such as the
[marketplace workflow](../marketplace/README.md). $api is the /api/v1 base URL,
$productId is that product and $sellerHeaders contains its verified seller token.
Do not log the token. Run from the feature checkout root. This demonstration
explicitly declares 500 g; it does not infer a real product's weight.

```powershell
$path = "$api/products/$productId/listing"
$draft = Invoke-RestMethod $path -Headers $sellerHeaders
$quantity = Get-Content backend/examples/unit-pricing/quantity.json -Raw | ConvertFrom-Json
$replacement = @{
    expected_revision = $draft.revision
    passport_publication_id = $draft.content.passport_publication_id
    seller_display_name = $draft.content.seller_display_name
    location = $draft.content.location
    summary = $draft.content.summary
    photos = $draft.content.photos
    selling_quantity = $quantity
}
Invoke-RestMethod $path -Method Put -Headers $sellerHeaders -ContentType 'application/json' -Body ($replacement | ConvertTo-Json -Depth 10)
$preview = Invoke-RestMethod "$path/preview" -Headers $sellerHeaders
$preview.publication_blockers
$preview.payload.selling_quantity | ConvertTo-Json
$preview.payload.unit_price | ConvertTo-Json
# Review the complete preview and its unverified-data notices before approving.
$approval = @{expected_revision=$preview.revision; preview_hash=$preview.preview_hash; approved=$true}
Invoke-RestMethod "$path/activate" -Method Post -Headers $sellerHeaders -ContentType 'application/json' -Body ($approval | ConvertTo-Json)
Invoke-RestMethod "$api/marketplace/listings/$($draft.id)"
```

A $17 selling price with 500 g in one loaf displays $34/kg. Checkout still charges
$17 per loaf. Existing approved listings without quantity remain visible with
unknown unit pricing. New/updated publication without a declaration returns 409
SELLING_QUANTITY_REQUIRED; private drafts remain saveable. Do not guess one item
or derive weight from a free-text unit label to bypass that requirement.
See the [full contract and frontend impact](../../../docs/standardized-unit-pricing.md).
