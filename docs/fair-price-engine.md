# Fair Price Engine: production economics v1

This is the numerical foundation of the Fair Price Engine. Market context,
seller quality constraints, and AI explanations will build on these calculations.
The current range expresses a seller's cost and margin assumptions; it does not
establish whether a price is fair to buyers. The seller chooses the final price.

## API contract

`POST /api/v1/pricing/analyze` returns HTTP 200 for valid inputs and HTTP 422
with field validation details for invalid inputs. `GET /health` returns
`{"status":"ok"}`. OpenAPI documents the request and response schemas.

All costs and prices use USD in this initial version. Send decimal values as
JSON strings to preserve precision; calculated decimals are returned as strings.
Rates are fractions: `"0.20"` is 20%. No exchange rates or PayPal fee schedule
are assumed. The example's processing fees are illustrative inputs only.

Required fields:

| Field | Meaning |
| --- | --- |
| `currency` | `USD` |
| `sellable_units` | Integer usable yield after loss or waste, from 1 to 1,000,000 |
| `costs` | Up to 200 batch-allocated costs: label, category, amount |
| `labor` | Up to 100 labor entries: label, hours, hourly_rate |
| `payment_fees` | Rate, fixed_per_order, integer units_per_order |
| `target_margin` | Minimum and maximum desired profit as a fraction of revenue |

Optional `proposed_prices` accepts up to 50 prices for simulation; omission
returns an empty scenario list. Empty costs and labor lists are permitted to
model incomplete data and produce missing-cost warnings. Explicit fee inputs
are required even when they are zero. Monetary inputs, hours, and rates accept
up to six decimal places; amounts and hours are bounded at one billion. Labels
must be nonblank and at most 200 characters. Unknown fields are rejected.

Cost categories: `materials`, `packaging`, `transport`, `utilities`, `equipment`,
`overhead`, `risk_reserve`, `other`. Each amount is the total allocated to this
batch. Include costs of consumed inputs even if some output is wasted. Allocate
equipment and overhead to the batch rather than entering the entire asset cost.
Enter labor only in the labor list to avoid double counting. Seller quality
requirements and material choices are not changed by the calculator.

Rates must be nonnegative and below one. Minimum margin must not exceed maximum;
processing rate plus maximum margin must be less than one. Negative values,
nonfinite decimals, zero yield, excessive precision, and oversized lists are
rejected. Units per order is a positive integer bounded at one million; it is
independent of batch yield and assumes all units share the same price and fee.

## Formulas and rounding

Let `C` be the batch cost including labor, `Y` sellable units, `r` the processing
rate, `f` the fixed fee per order, `q` units per order, and `m` the target margin.

```text
labor total = sum(hours * hourly rate)
C = sum(batch cost amounts) + labor total
unit cost = C / Y
allocated fixed fee = f / q
break-even price = (C / Y + f / q) / (1 - r)
price at target margin m = (C / Y + f / q) / (1 - r - m)
fee per unit at price p = p * r + f / q
profit per unit = p - fee per unit - C / Y
batch profit = profit per unit * Y
margin = profit per unit / p
markup = (p - C / Y) / (C / Y)
```

Markup is the conventional pre-fee markup on production cost; margin is after
modeled fees. Margin is null at zero revenue; markup is null at zero production
cost. Zero-revenue scenarios cannot satisfy a positive-revenue margin target.
Batch profit assumes all usable units sell, without discounts or returns.

Calculations use decimal arithmetic with isolated precision. Break-even and
range bounds round upward to USD cents so rounding does not undercut cost
recovery or the target margin. Other calculated details round half-up to six
decimal places at output only. Loss and margin flags use unrounded values.
Fees are proportional estimates: provider-specific transaction rounding, tax,
discounts, refunds, shipping charged to buyers, and currency conversion are not
modeled. Actual settlement profit needs reconciliation with payment records.

For the [sample request](../backend/examples/pricing-request.json), batch cost
is $100 and unit cost is $10. Allocated fixed fee is $0.25. Break-even is $10.57,
and the seller's 20%-30% target range is $13.32-$15.30. A $10 price loses $0.55
per unit. A $15 price earns $4.30 per unit after modeled fees: 28.666667% margin,
50% pre-fee markup, and $43 profit if the entire batch sells.

## Evidence and privacy boundaries

Every response identifies `production-economics-v1` and the
`seller_supplied_unverified` input basis. Warnings explicitly identify
unverified inputs, missing market evaluation, missing quality evaluation,
missing labor or overhead, and loss-making proposed prices. Absence of a
missing-cost warning does not prove the input amounts are complete or correct.

The stateless calculator does not call an LLM, recommend lower-quality substitutions, retrieve
competitor prices, publish a Fair Price Passport, or make autonomous business
decisions. Its endpoint does not persist submitted data or make payment transactions.
Calculation output contains private seller economics; it must not be exposed
as a public passport without a separate seller-approved disclosure policy.

Authenticated, seller-authorized product analysis routes provide a separate, explicit save
operation for private seller history. Saved records preserve validated inputs,
calculated results, the calculation version, and product metadata at creation.
Later product edits do not change those records. See the
[shared API integration proposal](api-contract.md); frontend acceptance is pending.

Product Quality Locks and saved quality evaluations are separate from pricing
analysis. Sellers can define mandatory boolean, allowed-choice, or numeric
requirements and check supplied alternative claims deterministically. Missing
claims and incompatible units/types remain unknown; a failed requirement fails
the check. No configured rules produces not_evaluated, not a pass. Every saved
evaluation preserves its rule revision and inputs, with
`seller_reported_unverified` basis. A pass does not verify the claims, certify
quality, or establish an acceptable cost saving. Pricing analysis still does not
evaluate quality and retains its existing warning.

Finished-product price observations and comparison reports are a separate private
API. Sellers enter source, location, date, quoted quantity/price, and quality notes;
the backend normalizes selected compatible quantities and flags stale/incompatible
evidence. Report ranges describe selected nominal quotes, not a representative
market sample or an objectively fair price. They do not verify quality equivalence
or feed automatically into production-economics calculations. Existing pricing
warnings about missing market and quality evaluation remain unchanged.

Seller pricing reviews now assemble an explicitly selected saved production
analysis, quality evaluations, and optional price-comparison report. They preserve
source snapshots and explain limitations deterministically. New reviews reassess
quote freshness and flag outdated quality checks. Cross-basis price assessments
require a seller-declared quantity for one production unit, with compatible units.
Review relations describe six-decimal displayed quote ranges, not a recommended
price. Review payloads remain private; all sources and claims remain unverified.

Fair Price Passports now provide seller-controlled disclosure projections from
private pricing reviews. Drafts and previews require seller ownership, and public
publication requires approval of an exact revision/hash. Costs and evidence
sections are hidden by default. Published payloads never forward raw reviews or
private source identifiers and can be withdrawn. Publication is disclosure
approval, not source verification, certification, or an objective fairness verdict.

## Backend priorities after this slice

1. General FairMade accounts default to buyer; seller access requires verification.
   Pending seller applications, private products, and analysis history are implemented
   for local development, with frontend contract review pending. Verification
   decisions, admin provisioning/monitoring, hosted account recovery, abuse controls,
   and operations remain future work.
2. Quality Locks and immutable claim-check history: implemented for local
   development, pending frontend contract review. Manually entered finished-product
   price evidence, limited exact quantity conversions, explicit provenance and
   freshness reporting are also implemented. Source verification, quality-aware
   benchmark selection, broader unit support, and explainable recommendations
   remain future work. Deterministic seller pricing reviews now connect saved
   economics, selected quality evidence, and price context with explicit unit
   mappings and evidence-gap explanations; they do not set prices or establish
   objective fairness.
3. Seller-controlled Fair Price Passport drafts, previews, approved publication,
   and withdrawal: implemented for local development, pending frontend contract
   review. Seller listing drafts, explicit activation/deactivation, public browse,
   text/type/location filters, and public detail APIs are now implemented. Listing
   prices come from approved Passports; publication withdrawal/supersession or loss
   of seller access hides linked listings. Availability and checkout remain deferred.
4. Orders, inventory reservation, and PayPal Sandbox checkout with verified,
   idempotent payment events and reconciled fees.
   Sellable-unit inventory, exact unpaid order snapshots, buyer/seller histories,
   cancellation, and expiring stock holds are now implemented for local development.
   Checkout still requires payment/merchant and fulfillment decisions. No order
   can be marked paid through these APIs.
5. Supplier intelligence and expanded business/shopping assistants.

Each milestone is a separate issue or feature worktree and reviewed PR.
