"""Build public catalog content only from explicit fields and an approved Passport."""

from fairmade.marketplace.schemas import CatalogContent, ListingContent
from fairmade.passports.schemas import PublicPassport, PublicPublication
from fairmade.photos.schemas import PublicPhoto
from fairmade.unit_pricing.service import calculate

NOTICES = [
    "Listing and location information are seller-reported and unverified.",
    "A listing does not confirm stock, delivery, fulfillment, or payment availability.",
]


def project(
    content: ListingContent, publication: PublicPublication, photos: list[PublicPhoto] | None = None
) -> CatalogContent:
    passport = PublicPassport.model_validate(publication.payload)
    unit_price = (
        calculate(passport.price.amount, content.selling_quantity)
        if content.selling_quantity is not None
        else None
    )
    notices = list(NOTICES)
    if unit_price is not None:
        notices.append("Unit prices use unverified seller-declared contents of one selling unit.")
        notices.append(
            "Comparable dimensions do not establish equivalent quality or objective value."
        )
        if unit_price.status == "below_display_precision":
            notices.append(
                "The positive unit price is below six-decimal display precision, not free."
            )
    return CatalogContent(
        product=passport.product,
        price=passport.price,
        seller_display_name=content.seller_display_name,
        location=content.location,
        summary=content.summary,
        passport_id=publication.id,
        passport_payload_hash=publication.payload_hash,
        notices=notices,
        photos=photos,
        selling_quantity=content.selling_quantity,
        unit_price=unit_price,
    )
