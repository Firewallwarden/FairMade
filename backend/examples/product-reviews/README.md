# Synthetic verified-purchase feedback

Use the feature backend migrated through 0018 and a backend-verified sandbox-paid
order belonging to `$buyerHeaders`. `$orderId` and `$listingId` come from its order
response. These commands do not create payments or grant seller access. Review
text is intentionally synthetic; never include personal addresses or payment data.

```powershell
$base = 'http://127.0.0.1:8000'
$source = "$base/api/v1/orders/$orderId/listings/$listingId/review"
$body = @{ rating = 4; text = 'Synthetic buyer opinion for local testing.'; publish = $true } | ConvertTo-Json
# Review the text first: publish=true makes it public immediately on a visible product.
$review = Invoke-RestMethod $source -Method Post -Headers $buyerHeaders -ContentType 'application/json' -Body $body
Invoke-RestMethod "$base/api/v1/marketplace/listings/$listingId/reviews"
Invoke-RestMethod "$base/api/v1/marketplace/listings/$listingId/reviews/summary"
```

Author management uses the general account session, including sellers buying from
other sellers. Neither the product's seller nor unrelated accounts may edit or
withdraw buyer feedback. There is one review per buyer/product, even after repeat
purchases; update the existing review instead of submitting another one.

```powershell
$ownPath = "$base/api/v1/account/product-reviews/$($review.id)"
$body = @{ expected_revision = $review.revision; rating = 3; text = 'Revised synthetic opinion.'; publish = $true } | ConvertTo-Json
$review = Invoke-RestMethod $ownPath -Method Put -Headers $buyerHeaders -ContentType 'application/json' -Body $body
$withdrawal = @{ expected_revision = $review.revision } | ConvertTo-Json
Invoke-RestMethod "$ownPath/withdraw" -Method Post -Headers $buyerHeaders -ContentType 'application/json' -Body $withdrawal
Invoke-RestMethod "$base/api/v1/account/product-reviews" -Headers $buyerHeaders
```

Reload after revision conflicts. PUT can explicitly republish withdrawn content
using the latest revision and publish=true. Captures verify sandbox purchase
evidence, not review claims, live seller earnings, identity or product quality.
Reviews remain independent of seller-reported pickup/refund decisions. Public
catalog withdrawal hides the whole product page; it never deletes reviews.
Moderation/reporting/appeals, abuse controls, privacy/retention, audit and browser
integration need later work; see [the full plan](../../../docs/product-reviews.md).
