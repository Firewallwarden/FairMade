"""Build public catalog content only from explicit fields and an approved Passport."""

from fairmade.marketplace.schemas import CatalogContent, ListingContent
from fairmade.passports.schemas import PublicPassport, PublicPublication

NOTICES = [
    "Listing and location information are seller-reported and unverified.",
    "A listing does not confirm stock, delivery, fulfillment, or payment availability.",
]


def project(content: ListingContent, publication: PublicPublication) -> CatalogContent:
    passport = PublicPassport.model_validate(publication.payload)
    return CatalogContent(
        product=passport.product,
        price=passport.price,
        seller_display_name=content.seller_display_name,
        location=content.location,
        summary=content.summary,
        passport_id=publication.id,
        passport_payload_hash=publication.payload_hash,
        notices=list(NOTICES),
    )
