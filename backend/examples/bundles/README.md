# Synthetic product pair examples

Replace every illustrative ID with current approved listings/revisions from one
published storefront and use a fresh request UUID for conversation creation.
Keep real financial/payment data out of demo fixtures.

POST request.json to /api/v1/buyer/bundles/suggest with a buyer session, or to
/api/v1/seller/bundles/suggest with that storefront owner's seller session.
The exact report works without AI. Seller history stays private. Buyer cart
payloads must be rechecked through ordinary order preview before purchase.

With the existing local assistant enabled, POST buyer-conversation.json to
/api/v1/assistants/conversations and ask a saved turn to explain the pair,
then why it does not prove a saving or complementary ingredients. For a seller
conversation use role seller and add the owned product_id of a supplied listing.
Render exact facts separately from model prose.

See [the full contract and handoff](../../../docs/product-bundle-suggestions.md).
