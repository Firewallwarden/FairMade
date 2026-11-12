# Shared PayPal sandbox setup and recovery

For the opt-in real provider workflow, use the
[credentialed verification checklist](../../../docs/paypal-verification.md).
It preserves isolated history and requires human sandbox buyer approval.

Development uses one shared sandbox merchant, as approved. Only the sandbox host
is implemented. Production will require seller-connected accounts through a
separately designed integration.

## Configure locally

Create/use a PayPal sandbox business account and a REST app belonging to that
account. Keep a different personal sandbox account for test buyer approval.
Find the app client ID/secret and the receiving business account's merchant ID.
Never paste secrets or credentials into chat, PRs, screenshots or logs.

Use [backend/.env.example](../../.env.example) as a template for process variables
in your PyCharm run configuration or local server environment:

- FAIRMADE_PAYPAL_ENABLED=true
- FAIRMADE_PAYPAL_ENVIRONMENT=sandbox
- FAIRMADE_PAYPAL_SANDBOX_CLIENT_ID: the app's client ID
- FAIRMADE_PAYPAL_SANDBOX_CLIENT_SECRET: its server-only secret
- FAIRMADE_PAYPAL_SANDBOX_MERCHANT_ID: the same sandbox business account's 13-character ID

The application reads process variables; it does not automatically load .env files.
Keep local credentials out of Git. The public client ID may be returned for SDK
initialization; the secret and OAuth tokens stay server-side. Live mode is rejected.
Apply Alembic migrations to current head using the server's database URL/environment.
Payment tables were introduced in 0009; later application migrations still apply.
Downgrade is refused if payment records exist; preserve the database and receipt/
retry history instead of deleting rows to bypass the guard.

## Backend/browser integration

Start from the [order workflow](../orders/README.md) but do not cancel the order.
Its variables are $api, $order and $buyerHeaders. The snippet below is synthetic
integration guidance. The [verification report](../../../docs/paypal-verification.md)
records the real backend recovery check and successful manual SDK browser purchase,
including tested revisions and limitations.

```powershell
$checkoutUrl = "$api/orders/$($order.id)/paypal-checkout"
Invoke-RestMethod -Uri "$api/paypal/config"
$checkout = Invoke-RestMethod -Method Post -Uri $checkoutUrl -Headers $buyerHeaders `
    -ContentType "application/json" -Body '{}'
$checkout.provider_order_id
# Let the buyer approve this ID through PayPal's supported sandbox JS SDK.
# A browser approval callback must then call the backend; it cannot mark paid.
Invoke-RestMethod -Method Post -Uri "$checkoutUrl/capture" -Headers $buyerHeaders `
    -ContentType "application/json" -Body '{}'
Invoke-RestMethod -Uri "$api/orders/$($order.id)" -Headers $buyerHeaders
```

The frontend owner implements SDK/browser integration separately. Supply the SDK
with the public client ID from config, currency USD, intent capture, and the
provider order ID returned by this backend. Never capture through browser-only
credentials or send client totals to the backend.

Verify a completed record, a paid order, one inventory deduction and consistent
history. Also try denying approval, double clicks, retries and an expired order.
The automated suite covers these through mocks. A successful credentialed browser
purchase is recorded in the verification report; configure and use that same SDK
flow in the demonstration. Opening a raw approval shortcut without its SDK
callback or a configured redirect return flow does not establish browser
completion, even when PayPal reports the order APPROVED.

## Recover uncertain results

POST $checkoutUrl/reconcile with {} and the buyer's bearer token. The receiving
seller can use POST /api/v1/seller/orders/{id}/paypal-checkout/reconcile with {}.
This performs authenticated provider reads, never a new capture POST.

If an operation is still leased, wait for its 60-second lease before retrying.
An APPROVED status means buyer consent, not payment. PENDING or unreachable
captures retain their stock hold even after the normal order deadline. Reconcile
before any manual action; never create a new order just because a capture timed out.
After six hours the backend refuses further capture POST retries and permits
reconciliation only.

needs_review means the data did not prove the expected payment or stock settlement.
Inspect the sandbox merchant's transaction history and preserve the local database.
Buyer full-refund requests with seller approval/denial now have a
[separate workflow](../refunds/README.md). Manual resolution of inconsistent
payment evidence is still not automated.
Do not clear records or force-release stock to make a payment appear successful.
These records track sandbox merchandise payments; shipping, tax, fulfillment,
partial refunds, production payouts and seller onboarding remain separate work.

Official references:
[Orders v2](https://developer.paypal.com/api/orders/v2),
[OAuth](https://developer.paypal.com/api/rest/authentication/),
[idempotency](https://developer.paypal.com/api/rest/reference/idempotency/),
and [Orders request-key retention](https://developer.paypal.com/sdk/orders/v2/orders-create/).
