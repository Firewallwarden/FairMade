export type DiscoveryFilters = {
  q: string; product_type: string; location: string; availability: string;
  sort: string; reference_unit: string; nearby: boolean;
  latitude: string; longitude: string; radius: string
}

function coordinate(value: string, maximum: number) {
  if (!/^-?\d+(\.\d{1,6})?$/.test(value) || Math.abs(Number(value)) > maximum)
    throw new Error(`Enter a coordinate within ±${maximum} with at most six decimal places.`)
  return value
}

export function nearbyListingRequest(filters: DiscoveryFilters, offset: number) {
  if (!/^\d+(\.\d)?$/.test(filters.radius) || Number(filters.radius) < 1 || Number(filters.radius) > 500)
    throw new Error('Radius must be 1–500 km with at most one decimal place.')
  return {
    origin: { latitude: coordinate(filters.latitude, 90), longitude: coordinate(filters.longitude, 180) },
    radius_km: filters.radius,
    ...(filters.q && { q: filters.q }),
    ...(filters.product_type && { product_type: filters.product_type }),
    ...(filters.availability && { availability: filters.availability }),
    ...(filters.sort && { sort: filters.sort }),
    ...(filters.reference_unit && { reference_unit: filters.reference_unit }),
    limit: 12, offset,
  }
}
