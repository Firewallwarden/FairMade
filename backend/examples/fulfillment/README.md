# Synthetic local pickup workflow

Use the feature backend migrated through 0017. `$sellerHeaders` and `$buyerHeaders`
are Authorization headers for a verified seller and the buyer on one genuinely
backend-verified sandbox-paid order. `$orderId` identifies that order. These examples
do not create payments, grant roles, send notifications or change stock.

```powershell
$base = 'http://127.0.0.1:8000'
$sellerPath = "$base/api/v1/seller/orders/$orderId/fulfillment"
$buyerPath = "$base/api/v1/orders/$orderId/fulfillment"
$progress = Invoke-RestMethod $sellerPath -Headers $sellerHeaders
foreach ($state in @('preparing', 'ready_for_pickup', 'collected')) {
    $body = @{
        expected_revision = $progress.revision
        state = $state
        pickup_instructions = 'Synthetic private pickup instructions; no real address.'
    } | ConvertTo-Json
    $progress = Invoke-RestMethod $sellerPath -Method Put -Headers $sellerHeaders -ContentType 'application/json' -Body $body
}
Invoke-RestMethod $buyerPath -Headers $buyerHeaders
Invoke-RestMethod "$buyerPath/history?limit=20&offset=0" -Headers $buyerHeaders
```

Only run the sequential loop for a new not_started order. Reload existing progress
and select its permitted next step instead of replaying earlier states. Retrying
the exact most recent body returns the same event; competing/stale edits require
reload. Instructions and history are private: never put them or bearer tokens in
URLs, analytics, public UI state or screenshots. Collected is seller-reported,
not buyer-confirmed pickup. A pending/approved refund blocks further updates but
preserves history. Shipping/delivery, fees, scheduling, reminders, confirmation
codes, disputes, returns/restocking and hosted retention controls remain future
work: see [the detailed plan](../../../docs/pickup-fulfillment.md).
