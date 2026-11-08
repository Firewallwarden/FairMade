# Public exact listing availability

The user chose exact available quantities after PR #33 opened and clarified that
this is a product disclosure decision, not an MVP/production distinction. Every
currently visible listing with compatible configured inventory publishes its exact
recorded available count. This choice has no planned automatic expiry or downgrade
to status-only disclosure.

Counts describe current seller-recorded sellable stock minus backend reservations.
They are not independent physical stock verification, supplier availability,
raw-material inventory or a reservation for the viewer. Checkout still checks
current stock and authoritative listing/order data.

## Response contract

Public CatalogCard/CatalogDetail responses add availability alongside the approved
payload, with the same projection used in storefront listings, nearby listing
results and currently visible saved-product cards:

    {
      "status": "available",
      "available_units": 8,
      "selling_unit": "loaf",
      "basis": "seller_recorded_stock_with_backend_reservations",
      "notice": "Based on seller-recorded stock; checkout rechecks availability."
    }

The fields mean:

- status: available when the known count is positive; unavailable when it is zero;
  unknown when inventory is absent, its unit does not match the approved listing,
  or inconsistent stock/reservation data would give a negative count.
- available_units: exact nonnegative whole sellable-unit count, at most 1,000,000,
  whenever status is known. Zero is explicitly returned as zero. For unknown
  status, the field is null or omitted according to the endpoint's existing
  exclude-none convention. Unknown is a data-completeness state.
- selling_unit: the approved public listing's unit. Private product edits cannot
  reinterpret it, and there is no implicit loaf/dozen/item conversion.
- basis/notice: seller-recorded inventory with backend reservation arithmetic,
  explicitly subject to a fresh stock check at checkout.

The response exposes available units only. It does not add on-hand totals,
reserved totals, stock revisions, hold/order/buyer IDs, private product IDs,
merchant/provider data or seller economics. Existing publication and seller-access
visibility gates apply before any card is returned.

Availability is live context outside the approved payload. It does not change
payload_hash, publication revision, approved prices, Passports, consent or photos.
Availability changes require no new price/disclosure publication because this
public-count policy was explicitly approved. Catalog, storefront, discovery and
favorites responses retain no-store behavior.

## Filters and pagination

| Endpoint | Filter |
| --- | --- |
| GET /api/v1/marketplace/listings | Optional availability query |
| GET /api/v1/storefronts/{storefront_id}/listings | Optional availability query |
| POST /api/v1/discovery/listings | Optional availability JSON field |

Allowed filter values are available, unavailable or unknown. Omitted/null uses all
visible listings. Invalid values produce 422. Existing text/type/location/radius
filters and bounded limit/offset semantics remain.

The availability projection and filter use the same SQL statement as listing
visibility, before pagination. Nearby filters also run before the 1,000-candidate
guard, exact-radius ranking and pagination. A broad filtered search still raises
SEARCH_TOO_BROAD when it exceeds that existing limit; results are not silently
truncated. Storefront discovery itself has no product-availability filter.

## Reservation and payment semantics

Available count is on_hand minus quantities in active unpaid holds. Ordinary
expired/cancelled holds do not reduce availability. Pending capture and unresolved
payment-review holds continue reducing it after the nominal order deadline,
matching the existing checkout/inventory policy.

Backend-verified capture deducts stock and releases that hold atomically; the
public projection does not subtract the paid quantity a second time. Approval in
a payment UI alone does not confirm capture. Refunds retain the existing explicit
restocking policy. Public reads create no orders, holds, payments or cleanup writes.

The shared active-hold predicate is used by private balances and public queries.
Reservation sums are grouped in SQL and joined to listing rows, with no per-card
stock queries. Summary filters and returned counts come from the same read rather
than independently reading a balance after filtering.

## Integration and operational follow-up

Backend endpoints are implemented proposals pending frontend acceptance; no UI
is included. No database migration, new service, dependency or infrastructure is
required. This independent feature starts from main and does not depend on the
pending production/recipe/review feature stack.

Consumers should render the exact count with its selling unit when known,
handle unknown explicitly, and retain checkout's final stock checks. Coordinate
browser/order integration and user-facing snapshot refresh behavior. Any future
change to disclosure policy needs a separate product decision.

Seller-connected live payments, hosted capacity/abuse controls and larger-scale
query/index tuning remain operational follow-up under their existing scopes.
Exact quantity disclosure itself is an approved ongoing product policy.
See the [synthetic workflow](../backend/examples/availability/README.md).
