"""Project a seller-approved draft through a closed public schema."""

from fairmade.storefronts.schemas import PublicStorefrontContent, StorefrontContent


def project(content: StorefrontContent) -> PublicStorefrontContent:
    return PublicStorefrontContent(
        display_name=content.display_name,
        description=content.description,
        location=content.location,
        notices=[
            "Profile and location information are seller-reported and unverified.",
            "A storefront is not identity verification or a product quality certification.",
            "Listings retain their separately approved seller names, prices and disclosures.",
        ],
    )
