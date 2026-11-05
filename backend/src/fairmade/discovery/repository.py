"""Bounded candidate queries use only the current approved area index and visibility."""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from fairmade.discovery.schemas import AreaSearch, ListingSearch
from fairmade.geography import bounding_box
from fairmade.marketplace.repository import visible_listings
from fairmade.models import MarketplaceListing, Product, Storefront, StorefrontDiscoveryLocation
from fairmade.storefronts.repository import visible

MAX_CANDIDATES = 1000


def area_predicates(body: AreaSearch):
    south, north, west, east = bounding_box(body.origin, body.radius_km)
    area = StorefrontDiscoveryLocation
    # Tiny outward tolerance protects candidates on a floating-point boundary.
    latitude = area.latitude_hundredths.between(south * 100 - 1e-7, north * 100 + 1e-7)
    if west <= east:
        longitude = area.longitude_hundredths.between(west * 100 - 1e-7, east * 100 + 1e-7)
    else:
        longitude = or_(
            area.longitude_hundredths >= west * 100 - 1e-7,
            area.longitude_hundredths <= east * 100 + 1e-7,
        )
    return latitude, longitude


def storefront_candidates(db: Session, body: AreaSearch) -> list[Storefront]:
    statement = (
        visible()
        .join(
            StorefrontDiscoveryLocation, StorefrontDiscoveryLocation.storefront_id == Storefront.id
        )
        .where(*area_predicates(body))
    )
    if body.q:
        statement = statement.where(
            Storefront.search_text.contains(body.q.casefold(), autoescape=True)
        )
    return list(db.scalars(statement.order_by(Storefront.id).limit(MAX_CANDIDATES + 1)))


def listing_candidates(db: Session, body: ListingSearch):
    visible_profiles = visible().with_only_columns(Storefront.id)
    statement = (
        visible_listings()
        .add_columns(Storefront)
        .join(Product, Product.id == MarketplaceListing.product_id)
        .join(Storefront, Storefront.account_id == Product.account_id)
        .join(
            StorefrontDiscoveryLocation, StorefrontDiscoveryLocation.storefront_id == Storefront.id
        )
        .where(Storefront.id.in_(visible_profiles), *area_predicates(body))
    )
    if body.q:
        statement = statement.where(
            MarketplaceListing.search_text.contains(body.q.casefold(), autoescape=True)
        )
    if body.product_type:
        statement = statement.where(MarketplaceListing.product_type == body.product_type)
    return db.execute(statement.order_by(MarketplaceListing.id).limit(MAX_CANDIDATES + 1)).all()
