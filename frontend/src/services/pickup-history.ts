import { privateRequest } from './session'
import { choice, integer, nullable, object, page, text, timestamp } from './decode'

export const getPickupHistory = (id: string, seller: boolean, offset: number, signal?: AbortSignal) =>
  privateRequest(`${seller ? '/seller' : ''}/orders/${id}/fulfillment/history?limit=20&offset=${offset}`, page(value => {
    const data = object(value)
    return { revision: integer(data.revision), state: choice(data.state, ['preparing', 'ready_for_pickup', 'collected'] as const), pickup_instructions: nullable(data.pickup_instructions, text), created_at: timestamp(data.created_at) }
  }), { signal })
