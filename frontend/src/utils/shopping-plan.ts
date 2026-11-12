import type {
  BasketNeed,
  BasketRequest,
} from '../services/planning-contract.ts'
export function buildBasketRequest(
  storefront: string,
  budget: string | null,
  needs: BasketNeed[],
): BasketRequest {
  if (needs.length < 1 || needs.length > 4)
    throw new Error('Choose one to four shopping needs.')
  const groups = new Set<string>(),
    listings = new Set<string>()
  for (const need of needs) {
    if (
      !/^[A-Za-z0-9_-]{1,32}$/.test(need.group_id) ||
      groups.has(need.group_id)
    )
      throw new Error('Each shopping need must be distinct.')
    groups.add(need.group_id)
    if (
      !Number.isSafeInteger(need.quantity) ||
      need.quantity < 1 ||
      need.quantity > 10000
    )
      throw new Error('Choose 1–10,000 selling units per need.')
    if (need.alternatives.length < 1 || need.alternatives.length > 4)
      throw new Error('Choose one to four acceptable alternatives per need.')
    for (const item of need.alternatives) {
      if (listings.has(item.listing_id))
        throw new Error(
          'Use a product in only one need, once. Alternatives are your choices, not proof of equivalence.',
        )
      listings.add(item.listing_id)
    }
  }
  return { storefront_id: storefront, budget, needs }
}
