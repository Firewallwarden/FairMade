"""Distance and conservative search bounds at the equator, poles and dateline."""

from decimal import Decimal

import pytest

from fairmade.geography import SearchOrigin, bounding_box, distance_km


@pytest.mark.parametrize(
    ("origin", "target", "expected"),
    [
        ((0, 0), (0, 0), 0),
        ((0, 0), (0, 1), 111.195),
        ((0, 179.9), (0, -179.9), 22.239),
        ((90, 0), (90, 180), 0),
        ((0, 0), (0, 180), 20015.114),
    ],
)
def test_distance_known_cases(origin, target, expected):
    point = SearchOrigin(latitude=str(origin[0]), longitude=str(origin[1]))
    assert distance_km(point, *target) == pytest.approx(expected, abs=0.001)


@pytest.mark.parametrize("latitude", [-90, -89, -45, 0, 45, 89, 90])
@pytest.mark.parametrize("longitude", [-180, -179.9, 0, 179.9, 180])
def test_bounds_include_sampled_points_within_radius(latitude, longitude):
    origin = SearchOrigin(latitude=str(latitude), longitude=str(longitude))
    south, north, west, east = bounding_box(origin, Decimal("500"))
    for lat_delta in (-4, -1, 0, 1, 4):
        target_lat = max(-90, min(90, latitude + lat_delta))
        for lon_delta in (-180, -10, -1, 0, 1, 10, 180):
            target_lon = (longitude + lon_delta + 180) % 360 - 180
            if distance_km(origin, target_lat, target_lon) <= 500:
                assert south - 1e-9 <= target_lat <= north + 1e-9
                if west <= east:
                    assert west - 1e-9 <= target_lon <= east + 1e-9
                else:
                    assert target_lon >= west - 1e-9 or target_lon <= east + 1e-9
