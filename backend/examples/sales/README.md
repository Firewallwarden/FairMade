# Synthetic sales and estimated profit

Use only disposable local data and the approved shared PayPal sandbox merchant.
No production payouts or verified accounting profit are represented. All source
costs remain seller-reported, potentially incomplete and unverified.

Run migration 0012 using the backend's documented upgrade command. These
PowerShell examples run from the worktree root and assume `$api`, the verified
seller's `$authHeaders`, an owned `$product`, and its saved `$analysis` from the
[seller workflow](../seller-workflow.md). Registration alone still grants buyer
access; these examples do not grant roles. See the
[full reporting contract](../../../docs/api-contract.md#private-seller-sales-and-estimated-profitability).

## Choose the estimate before an order is created

```powershell
$costUrl = "$api/products/$($product.id)/sales-cost-basis"
$selected = Invoke-RestMethod -Uri $costUrl -Headers $authHeaders
$selectionBody = @{
    expected_revision = $selected.revision
    analysis_id = $analysis.id
} | ConvertTo-Json
$selected = Invoke-RestMethod -Method Put -Uri $costUrl -Headers $authHeaders -ContentType 'application/json' -Body $selectionBody
$selected | ConvertTo-Json -Depth 10
```

The saved analysis must belong to this product and match its current selling-unit
label and product type. Its production costs include labor and cost categories,
but exclude estimated payment fees. No cost analysis is chosen automatically.

Create a new order and complete the
[sandbox payment workflow](../paypal/README.md). The private cost estimate freezes
when the order is created, alongside its inventory reservation. Selecting costs
after creating the order will not alter that order. Missing costs never prevent
checkout but leave estimated profit unavailable.

## Read the current capture cohort

```powershell
$startDate = [DateTime]::UtcNow.Date.AddDays(-30).ToString('yyyy-MM-dd')
$endDate = [DateTime]::UtcNow.Date.AddDays(1).ToString('yyyy-MM-dd')
$salesQuery = "start_date=$startDate&end_date=$endDate"
$salesUrl = "$api/seller/sales"
$summary = Invoke-RestMethod -Uri "$($salesUrl)?$salesQuery" -Headers $authHeaders
$summary | ConvertTo-Json -Depth 10
$page = Invoke-RestMethod -Uri "$salesUrl/orders?$salesQuery&limit=20&offset=0" -Headers $authHeaders
$page.items | ConvertTo-Json -Depth 20
```

The range includes its start UTC day and excludes its end UTC day. It selects
sales by backend capture-verification time; completed refunds for those sales
are included as currently known, even if refunded after the selected period.
This is not a statement of cash movements or actual merchant payouts during the
period. Over 1,000 matching sales returns REPORT_TOO_LARGE: narrow the period or
use the paginated detail endpoint.

For the original synthetic pricing fixture, batch cost is $100 across 10 loaves.
An order for two loaves at $17 each, with a verified $1 capture fee, produces $34
gross sales − $1 fee − $20 production cost = $13 estimated profit. Margin is
0.382353. A completed full refund gives −$21 estimated profit and null margin;
production cost and the original capture fee are retained. The $1 fee here is
illustrative/test-double data, not a real PayPal rate or fee guarantee.

Missing fees, missing/incompatible costs and unresolved refunds produce null
estimated profit. Use missing_fee_count, missing_cost_count and
unresolved_refund_count alongside known subset totals. covered_estimated_profit
only covers eligible sales, never the entire period when coverage is incomplete.

## Clear the selection for future orders

```powershell
$selected = Invoke-RestMethod -Uri $costUrl -Headers $authHeaders
$clearBody = @{ expected_revision = $selected.revision; analysis_id = $null } | ConvertTo-Json
Invoke-RestMethod -Method Put -Uri $costUrl -Headers $authHeaders -ContentType 'application/json' -Body $clearBody
```

Stale selections return REVISION_CONFLICT. Reload and review the selection before
retrying. Later analysis/product edits, clearing selections, refunds and restarts
do not rewrite saved cost snapshots. Historical orders without a snapshot remain
unknown. No cost snapshot is included in buyer orders, listings or public Passports.
