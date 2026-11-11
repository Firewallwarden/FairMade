# Ingredient and material declarations and explanations

Implemented additive backend proposal; frontend acceptance and browser integration
are pending. This extends existing Passport drafts/publications and assistant
sources; there is no new endpoint, provider, migration or business mutation.
Public declarations and private production recipes are separate evidence.

## Explicit public disclosure

Existing POST /api/v1/products/{product_id}/passports and revision-safe PUT
/api/v1/products/{product_id}/passports/{draft_id} accept optional composition
and disclosures.include_composition (strict boolean, default false). Example
content fragment, merged with the existing required review_id/title/price:

```json
{
  "disclosures":{"include_composition":true},
  "composition":{
    "completeness":"partial",
    "items":[
      {
        "label":"Seller-declared flour",
        "kind":"ingredient",
        "reported_role":"Seller's structure claim",
        "reported_specification":"Seller-reported flour grade",
        "declared_quantity":{"value":"400","unit":"g"}
      },
      {"label":"Paper wrap","kind":"packaging","reported_role":"Packaging declaration"}
    ]
  }
}
```

composition is null/omitted by default. When provided it contains completeness,
either partial (default) or seller_declared_complete, and one through twenty
items. Each item contains:

- label: one through two hundred trimmed characters.
- kind: ingredient, material, packaging or other.
- optional reported_role/reported_specification: one through two hundred trimmed
  printable characters each. Labels must also be printable; controls, multiline
  text and lone surrogates are rejected. Render these untrusted strings as text.
- optional declared_quantity: the existing bounded SellingQuantity shape, with
  decimal-string value and supported g/kg/ml/l/egg/dozen/loaf/item units. It is
  the seller's stated amount per published selling unit. Existing whole-count
  validation and the sixty-four-character numeric text bound apply. No totals,
  percentages, ingredient proportions or recipe reconciliation are inferred.

Component labels must be distinct case-insensitively within each kind. Unknown
fields, unsupported values, duplicates and exceeded limits return redacted 422
errors. include_composition true requires actual composition data. Private
Passport responses/errors now consistently use no-store, and Passport validation
omits raw input values. Existing authentication, seller role and ownership apply.

Providing data alone does not publish it. The normal exact-preview hash,
explicit approval and immutable publication workflow still applies. When
include_composition is false, the public projection omits composition even if a
private draft contains it. The old public payload, notices and digest remain
identical. Existing publications are not backfilled. Editing a private draft
does not change its approved snapshot. Enabling or changing a declaration needs
a fresh matching preview approval, followed by the existing separate listing
activation flow. Public version identifiers remain compatible optional extensions.
The existing DraftContent OpenAPI component name is preserved for generated clients.

Approved composition appears in the public Passport payload, including the
Passport nested in marketplace listing detail. It is not added to listing cards
or automatically copied from recipes, inventory, supplier claims or private cost
data. There is no source crawl, ingredient guessing or background disclosure.
Withdrawal/supersession retains existing visibility rules. Historical approved
business snapshots retain their existing persistence policy; conversation expiry
does not erase business records.

## Meaning and buyer explanations

All contents, roles, specifications, quantities and completeness are
seller-reported and unverified. seller_declared_complete is a seller statement,
not independently verified completeness, an allergen certificate or a safety
finding. Missing/partial declarations remain unknown. Product names, costs,
production inputs and the absence of a named item must not establish final
ingredients, allergens, nutrition, health benefits, compatibility or suitability.
Mandatory quality, safety and ethical requirements remain binding.

The existing buyer assistant uses only the current approved listing/Passport
allowlist. No extra option is needed. Its qualitative view receives declaration
status, labels, kinds, reported roles/specifications and completeness, with clear
source limitations. Exact declared quantities are omitted from model context and
rendered separately as server-calculated facts, linked to the existing public
listing evidence key. Existing non-disclosed Passports explicitly provide a
not_disclosed status to the model, rather than inviting inference from names.
This is a grounded explanation feature, not a general ingredient encyclopedia.

Saved buyer conversations retain listing scope and survive restarts. Private
recipe changes do not alter buyer evidence or expose private inputs. Source
withdrawal/replacement and approved listing changes retain the existing current
evidence and stale-answer rules. AI prose is not proof of every cited claim;
the frontend must distinguish declarations from verified facts and preserve
ordinary answer-review notices.

## Private seller production-input explanations

POST /api/v1/assistants/seller and saved seller scopes accept optional
include_recipe_inputs, a strict boolean defaulting to false. Example with a
synthetic illustrative owned product ID:

```json
{
  "product_id":"59a9818e-37a5-47c0-9302-b1b54ab67514",
  "include_recipe_inputs":true,
  "question":"Explain the recorded input evidence without inferring final ingredients."
}
```

When opted in, the owning seller receives evidence titled Private recorded
recipe production inputs. Its basis is seller_recorded_unverified. Data includes
product_id, status, inputs and policy. A current recorded recipe adds
recipe_revision, sellable_units and each input's label/raw_quantity. The numeric
quantity describes whole-recipe raw usage, including waste; it is not a declared
quantity in each finished product. Current product-unit edits do not relabel the
recipe yield. Feed or processing aids must never become inferred egg ingredients.

The projection omits purchase costs, purchase dates/quantities, instructions,
labor and notes. Other already selected seller economic evidence keeps its
existing rules. The model gets input labels, status and limitations only; exact
raw quantities/yield appear in server facts. Missing recipes return missing_recipe
with no invented inputs. More than twenty recorded ingredients returns 409
RECIPE_EXPLANATION_TOO_LARGE before inference, rather than a partial projection.
The underlying recipe API's larger limit is unchanged.

Owners, current seller roles and sessions are checked. Buyers cannot supply
this private option or read recipe data. Saved seller follow-ups recompute recipe
revision/input evidence after restarts; changes withhold stale answers. An
inference-time recipe change or revoked session cannot save a stale private
answer. Existing source/response-size/conversation bounds still apply.
No recipe, stock, cost analysis, Quality Lock or publication is changed.

## Later depth

Recommended current behavior uses manual, exact seller-approved declarations and
explicit private source selection. Later optional enhancements include reviewed
recipe-to-declaration proposals with clear production-input distinctions, verified
ingredient/material evidence, curated source-backed explanations, richer taxonomy,
localized quantities, completeness/correction workflows and source retention
review. Allergen, nutrition, safety or suitability verification would need its
own evidence and policy. No paid provider or new infrastructure is implied.
See DOMAIN-013 in [the decision register](local-mvp-decisions.md).
