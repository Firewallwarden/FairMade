# Synthetic marketplace workflow

For local development only. Run in PowerShell with the migrated backend running.
Use an account already granted seller access through the approved verification
process. New registrations/pending applications do not gain it. Automated tests
seed synthetic grants; there is no public role-grant endpoint.

First complete the [Passport workflow](../passports/README.md), including explicit
publication, and stop before its withdrawal example. The script below assumes
its `$api`, `$authHeaders`, `$product`, and `$published` variables remain in scope.
Never put real bearer tokens in checked-in scripts or transcripts.

```powershell
$listingUrl = "$api/products/$($product.id)/listing"
$listingContent = @{
    passport_publication_id = $published.id
    selling_quantity = @{ value = '1'; unit = 'loaf' }
    seller_display_name = "Example bakery"
    location = "Exampletown"
    summary = "Synthetic local-development listing."
}
$listing = Invoke-RestMethod -Method Post -Uri $listingUrl -Headers $authHeaders `
    -ContentType "application/json" -Body ($listingContent | ConvertTo-Json)

# Private draft: no public listing exists until this exact preview is approved.
$preview = Invoke-RestMethod -Uri "$listingUrl/preview" -Headers $authHeaders
$preview.payload | ConvertTo-Json -Depth 20
# Inspect the quantity, calculated unit price, title, display fields and notices.
$approval = @{
    expected_revision = $preview.revision
    preview_hash = $preview.preview_hash
    approved = $true
}
Invoke-RestMethod -Method Post -Uri "$listingUrl/activate" -Headers $authHeaders `
    -ContentType "application/json" -Body ($approval | ConvertTo-Json)

# Anonymous reads need no bearer token.
Invoke-RestMethod -Uri "$api/marketplace/listings?q=loaf&limit=20&offset=0"
Invoke-RestMethod -Uri "$api/marketplace/listings/$($listing.id)"

Invoke-RestMethod -Method Post -Uri "$listingUrl/deactivate" -Headers $authHeaders
```

All example text is synthetic and unverified. The listing cannot submit its own
price; title/type/unit/price come from its approved Passport. Display name,
location, and summary are explicit public inputs, never private product text or
email. Treat them as plain text in the browser.

Use PUT with the full content plus expected_revision to edit privately.
Inspect and approve a fresh preview to update public content. Deactivation
invalidates earlier approval. Withdrawing or superseding the linked Passport
hides the listing; select the new Passport in the draft and approve again.

An active listing is discoverable; it does not confirm stock, delivery, payment,
or independently verified seller claims. Anonymous reads set no-store; copies
already received by clients cannot be recalled. See the
[proposed API contract](../../../docs/api-contract.md) for fields and errors.
