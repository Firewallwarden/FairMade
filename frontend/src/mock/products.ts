import type { Product } from '../types/product'

// Illustrative products and USD prices, not live local listings or verified claims.
export const featuredProducts: Product[] = [
  {
    id: 'eggs',
    name: 'Backyard eggs',
    maker: 'The little backyard flock',
    category: 'From the coop',
    price: 6,
    image: '/images/backyard-eggs.jpg',
    imageAlt:
      'A carton of brown, cream, and pale blue eggs on a rustic surface',
    note: 'One dozen · sample listing',
  },
  {
    id: 'bread',
    name: 'The weekend loaf',
    maker: 'A neighborhood bread kitchen',
    category: 'From the oven',
    price: 9,
    image: '/images/market-bread.jpg',
    imageAlt: 'Rustic seeded and flour-dusted loaves with wheat stalks',
    note: 'One loaf · sample listing',
  },
  {
    id: 'soap',
    name: 'A little botanical soap',
    maker: 'The cottage soap bench',
    category: 'Made by hand',
    price: 7,
    image: '/images/botanical-soap.jpg',
    imageAlt: 'Handmade soap bars arranged with botanical ingredients',
    note: 'One bar · sample listing',
  },
  {
    id: 'flowers',
    name: 'The cottage garden bunch',
    maker: 'The garden at the end of the lane',
    category: 'From the garden',
    price: 14,
    image: '/images/white-tulip-bouquet.jpg',
    imageAlt:
      'White tulips and green leaves wrapped in brown paper on a rustic wooden table',
    note: 'One bunch · sample listing',
  },
]
