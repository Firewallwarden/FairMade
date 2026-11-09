import { featuredProducts } from '../mock/products'
import type { Product } from '../types/product'
// Replace with apiRequest<Product[]> after agreeing on the FastAPI contract.
export function getFeaturedProducts(): Product[] { return featuredProducts }
