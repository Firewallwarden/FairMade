# Fair Price Passport workflow

Use an existing seller account, owned product, and pricing review. These operations
do not create seller roles. Examples and amounts are synthetic. No actual seller
data is published by the development workflow unless the seller calls publish.

```powershell
$passportsUrl = "$api/products/$($product.id)/passports"
$draftBody = @{
    review_id = $review.id
    title = 'Synthetic public loaf'
    price = '17.00'
    disclosures = @{}
} | ConvertTo-Json -Depth 10
$draft = Invoke-RestMethod -Method Post -Uri $passportsUrl -Headers $authHeaders -ContentType 'application/json' -Body $draftBody
$draftUrl = "$passportsUrl/$($draft.id)"
$preview = Invoke-RestMethod -Uri "$draftUrl/preview" -Headers $authHeaders
$preview.payload
```

Inspect the payload. Empty disclosures hide all private costs and evidence
sections. Opting into cost_categories shares only the selected enum-category
per-unit totals, never raw entries. Other optional switches are include_labor,
include_unit_cost, include_quality_requirements, include_quality_summary, and
include_market_context. All flags are strict booleans and default false.

Replace a draft using PUT with its complete content and expected_revision. A
successful edit increments revision. Review its new preview before approval;
do not blindly retry a stale approval.

After the seller explicitly approves the displayed payload:

```powershell
$approval = @{
    expected_revision = $preview.revision
    preview_hash = $preview.preview_hash
    approved = $true
} | ConvertTo-Json
$published = Invoke-RestMethod -Method Post -Uri "$draftUrl/publish" -Headers $authHeaders -ContentType 'application/json' -Body $approval
Invoke-RestMethod -Uri "$api/passports/$($published.id)"
Invoke-RestMethod -Uri "$draftUrl/publications" -Headers $authHeaders
# Remove this snapshot from public API access:
Invoke-RestMethod -Method Post -Uri "$draftUrl/publications/$($published.id)/withdraw" -Headers $authHeaders
```

Publication stores the exact preview, hash, revision and approving account
internally. Public JSON does not include private account, product, review,
draft or source IDs. A new publication supersedes the previous active one for
the product. Editing a draft does not alter its existing approved snapshot;
publish or withdraw explicitly to change public visibility.

Withdrawn/superseded snapshots return 404 publicly. A withdrawn revision cannot
be restored by retrying publish; edit to a new revision and approve its preview.
Prior client copies cannot be erased. Public responses use no-store caching.

Market summaries are aggregate historical context only; raw quote sources and
locations remain private. Quality summaries retain failure/unknown/outdated
counts without private candidate identities. Requirements are seller-defined
claims, never certifications. Free-text public descriptions are seller-written
and must be rendered as text by clients.
