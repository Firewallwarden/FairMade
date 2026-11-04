# Buyer refund request and seller review

Local development only, using the approved shared PayPal sandbox merchant.
Complete the [sandbox payment workflow](../paypal/README.md) first and verify
the order is paid. Keep $api, $order, $buyerHeaders and the receiving seller's
$authHeaders in scope. Examples are synthetic; never put credentials in transcripts.

This slice supports one full-order request per paid order. Approval and denial
are final seller decisions. Partial refunds, resubmission/appeals, return tracking
and automatic inventory restocking are separate future features.

## Request and review

```powershell
$refundUrl = "$api/orders/$($order.id)/refund-request"
$sellerRefundUrl = "$api/seller/orders/$($order.id)/refund-request"
$requestBody = @{ reason = "Synthetic buyer reason for requesting a full refund." }
$refund = Invoke-RestMethod -Method Post -Uri $refundUrl -Headers $buyerHeaders `
    -ContentType "application/json" -Body ($requestBody | ConvertTo-Json)
$review = Invoke-RestMethod -Uri $sellerRefundUrl -Headers $authHeaders
$review | ConvertTo-Json -Depth 10
Invoke-RestMethod -Uri "$api/seller/refund-requests?limit=20&offset=0" -Headers $authHeaders
```

Only the order's buyer can request it; only the verified receiving seller can
approve or deny. Both can read their private history. Reasons are plain text and
are not sent to PayPal. The buyer cannot choose an amount or approve the refund.

Choose one decision. To approve the reviewed request:

```powershell
$approvalBody = @{ expected_revision = $review.revision } | ConvertTo-Json
$result = Invoke-RestMethod -Method Post -Uri "$sellerRefundUrl/approve" `
    -Headers $authHeaders -ContentType "application/json" -Body $approvalBody
$result | ConvertTo-Json -Depth 10
```

Alternatively, for an undecided request, deny with an explanation:

```powershell
$denialBody = @{
    expected_revision = $review.revision
    reason = "Synthetic seller explanation for the denial."
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$sellerRefundUrl/deny" -Headers $authHeaders `
    -ContentType "application/json" -Body $denialBody
```

Do not execute both decisions on the same request. Approval initiates a full
sandbox refund, but only verified provider COMPLETED becomes refunded.
PENDING, an approval response, or a timeout does not prove money was returned.
The original capture history stays intact, and stock is never automatically added
back. The seller can separately adjust inventory only after determining goods
are actually sellable.

## Recover and validate

If the refund ID is known, either participant can reconcile it without initiating
another refund:

```powershell
Invoke-RestMethod -Method Post -Uri "$refundUrl/reconcile" -Headers $buyerHeaders `
    -ContentType "application/json" -Body '{}'
Invoke-RestMethod -Method Post -Uri "$sellerRefundUrl/reconcile" -Headers $authHeaders `
    -ContentType "application/json" -Body '{}'
Invoke-RestMethod -Uri "$api/orders/$($order.id)" -Headers $buyerHeaders
```

For an unknown result without a refund ID, the seller may retry the original
approval body. Use decision_expected_revision from the current record if the
original body was lost. The server reuses the same durable request key; never
create another payment/refund record to bypass uncertainty. Wait for the 60-second
lease after a crash. After six hours, unknown results require manual review;
existing refund IDs remain reconcilable.

Verify the seller decision, completed refund receipt, order status, unchanged
capture history and unchanged stock. Also test denial, stale/concurrent decisions,
permission failures, pending results and uncertain retries. Automated tests cover
these with provider doubles/HTTP mocks; a real sandbox/browser test still requires
local credentials and the frontend integration.

Apply migrations with the server stopped and preserve financial history.
Migration 0010 refuses downgrade once payment/refund rows exist; do not delete
records to bypass this protection.

See the [proposed API contract](../../../docs/api-contract.md) and the official
[PayPal Payments v2 reference](https://developer.paypal.com/api/payments/v2).
