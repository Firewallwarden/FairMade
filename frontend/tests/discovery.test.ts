import assert from 'node:assert/strict'
import { test } from 'node:test'
import { nearbyListingRequest } from '../src/services/discovery-contract.ts'
const filters = { q: 'bread', product_type: 'sourdough', location: 'unused label', availability: 'available', sort: 'unit_price', reference_unit: 'loaf', nearby: true, latitude: '40.123456', longitude: '-89', radius: '25.5' }
test('nearby discovery preserves supported ordering and pagination without unsupported location labels', () => {
  const body = nearbyListingRequest(filters, 24)
  assert.equal(body.offset, 24)
  assert.equal(body.sort, 'unit_price')
  assert.equal(body.reference_unit, 'loaf')
  assert.deepEqual(body.origin, { latitude: filters.latitude, longitude: '-89' })
  assert.equal('location' in body, false)
})
test('origin and radius reject out-of-bounds or over-precision values before transport', () => {
  for (const change of [{ latitude: '91' }, { longitude: '-181' }, { latitude: '40.1234567' }, { radius: '0' }, { radius: '501' }, { radius: '12.25' }])
    assert.throws(() => nearbyListingRequest({ ...filters, ...change }, 0))
})
