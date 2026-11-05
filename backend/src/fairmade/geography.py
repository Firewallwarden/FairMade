"""Approximate public area points and spherical distance helpers; no geocoding."""

import math
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field

from fairmade.pricing.schemas import Contract, Label

Latitude = Annotated[Decimal, Field(ge=-90, le=90, decimal_places=6, allow_inf_nan=False)]
Longitude = Annotated[Decimal, Field(ge=-180, le=180, decimal_places=6, allow_inf_nan=False)]
EARTH_RADIUS_KM = 6371.0088


class SearchOrigin(Contract):
    latitude: Latitude
    longitude: Longitude


class ApproximateArea(Contract):
    basis: Literal["seller_chosen_approximate"] = "seller_chosen_approximate"
    label: Label
    latitude: Annotated[Decimal, Field(ge=-90, le=90, decimal_places=2, allow_inf_nan=False)]
    longitude: Annotated[Decimal, Field(ge=-180, le=180, decimal_places=2, allow_inf_nan=False)]


def distance_km(origin: SearchOrigin, latitude: float, longitude: float) -> float:
    """Great-circle distance between representative points, not road/travel distance."""
    origin_latitude = math.radians(float(origin.latitude))
    target_latitude = math.radians(latitude)
    latitude_delta = target_latitude - origin_latitude
    longitude_delta = math.radians(longitude - float(origin.longitude))
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(origin_latitude) * math.cos(target_latitude) * math.sin(longitude_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, max(0.0, haversine))))


def bounding_box(origin: SearchOrigin, radius_km: Decimal) -> tuple[float, float, float, float]:
    """Conservative spherical bounds; west > east means an antimeridian crossing."""
    latitude = float(origin.latitude)
    longitude = float(origin.longitude)
    angular_radius = float(radius_km) / EARTH_RADIUS_KM
    latitude_delta = math.degrees(angular_radius)
    south = max(-90.0, latitude - latitude_delta)
    north = min(90.0, latitude + latitude_delta)
    if south == -90 or north == 90:
        return south, north, -180.0, 180.0
    longitude_delta = math.degrees(
        math.asin(min(1.0, math.sin(angular_radius) / math.cos(math.radians(latitude))))
    )
    west = (longitude - longitude_delta + 180) % 360 - 180
    east = (longitude + longitude_delta + 180) % 360 - 180
    return south, north, west, east
