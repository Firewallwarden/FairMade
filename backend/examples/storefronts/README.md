# Synthetic seller profile and storefront

Local development only. Run migration 0014 first. A verified seller can create
one storefront per account for the MVP; registration alone creates a buyer and
these examples do not grant roles.

Run these PowerShell blocks from the worktree root with the existing `$api`
and seller `$authHeaders` from the [account workflow](../seller-workflow.md).
All profile names, descriptions and places below are synthetic, unverified data.
See the [storefront API contract](../../../docs/api-contract.md#seller-profiles-and-storefronts).

## Create a private draft and inspect its exact preview

```powershell
$storesUrl = "$api/seller/storefronts"
$content = @{
    display_name = 'Example bakery'
    description = 'Synthetic independent seller profile for local testing.'
    location = 'Exampletown'
}
$store = Invoke-RestMethod -Method Post -Uri $storesUrl -Headers $authHeaders -ContentType 'application/json' -Body ($content | ConvertTo-Json)
$storeUrl = "$storesUrl/$($store.id)"
$preview = Invoke-RestMethod -Uri "$storeUrl/preview" -Headers $authHeaders
$preview | ConvertTo-Json -Depth 10
```

The draft is private. Its public UUID differs from the account UUID. A duplicate
create returns STOREFRONT_LIMIT; use GET on the private collection to find and
edit the existing storefront, including after withdrawal.

## Approve and inspect the public storefront

```powershell
$approval = @{
    expected_revision = $preview.revision
    preview_hash = $preview.preview_hash
    approved = $true
} | ConvertTo-Json
$published = Invoke-RestMethod -Method Post -Uri "$storeUrl/publish" -Headers $authHeaders -ContentType 'application/json' -Body $approval
$publicUrl = "$api/storefronts/$($store.id)"
Invoke-RestMethod -Uri $publicUrl
Invoke-RestMethod -Uri "$publicUrl/listings?limit=20&offset=0"
Invoke-RestMethod -Uri "$api/storefronts?q=Example&location=Exampletown"
```

Only currently visible listings owned by this account are grouped here.
Storefront publication does not activate product drafts or reserve stock.
Existing listing names, prices and Passport disclosures are not rewritten.
Profile/location claims are self-reported, not identity or quality certification.

## Edit and withdraw

```powershell
$store = Invoke-RestMethod -Uri $storeUrl -Headers $authHeaders
$replacement = @{
    expected_revision = $store.revision
    display_name = 'Updated example bakery'
    description = 'Synthetic revised profile, not public until approved.'
    location = 'Exampletown'
} | ConvertTo-Json
Invoke-RestMethod -Method Put -Uri $storeUrl -Headers $authHeaders -ContentType 'application/json' -Body $replacement
# Review a new preview and approve it to change the public version.
$preview = Invoke-RestMethod -Uri "$storeUrl/preview" -Headers $authHeaders
Invoke-RestMethod -Method Post -Uri "$storeUrl/withdraw" -Headers $authHeaders
```

Editing leaves the old approved public payload/search fields intact until approval.
Withdrawal hides the profile and increments its revision; any previously prepared
approval is stale. A new preview and explicit approval can republish the same UUID.
Repeated withdrawal is idempotent. Loss of seller access hides public storefront
views too. Independently approved catalog listings stay governed by their own
listing/Passport visibility rules.

Multiple storefronts, precise map coordinates, profile media/contact fields and
production verification are deferred. The stable storefront resource and plural
private collection form the foundation for later growth.
