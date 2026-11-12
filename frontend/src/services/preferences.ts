import { privateRequest } from './session'
import { boolean, integer, list, object, text } from './decode'
import {
  decodeBuyerProfile,
  decodeMemoryProposal,
  decodePreferences,
} from './preferences-contract'
import type { BuyerPreferences } from './preferences-contract'
import { decodeDetail } from './catalog-contract'
export const getBuyerProfile = (signal?: AbortSignal) =>
  privateRequest('/buyer/personalization', decodeBuyerProfile, { signal })
export const saveBuyerPreferences = (
  revision: number,
  preferences: BuyerPreferences,
) =>
  privateRequest('/buyer/personalization', decodeBuyerProfile, {
    method: 'PUT',
    json: {
      expected_revision: revision,
      enabled: true,
      confirmed: true,
      preferences,
    },
  })
export const disableBuyerPreferences = (revision: number) =>
  privateRequest('/buyer/personalization', decodeBuyerProfile, {
    method: 'PUT',
    json: {
      expected_revision: revision,
      enabled: false,
      confirmed: true,
      preferences: {},
    },
  })
export const deleteBuyerPreferences = (revision: number) =>
  privateRequest('/buyer/personalization', decodeBuyerProfile, {
    method: 'DELETE',
    json: { expected_revision: revision },
  })
export const proposeBuyerMemory = (conversation: string, turn: string) =>
  privateRequest('/buyer/personalization/remember', decodeMemoryProposal, {
    method: 'POST',
    json: { conversation_id: conversation, turn_id: turn },
    timeoutMs: 150000,
  })
export const getPersonalizedSuggestions = (unknownAvailability: boolean) =>
  privateRequest(
    '/buyer/personalization/suggestions',
    (value) => {
      const data = object(value)
      return {
        personalized: boolean(data.personalized),
        profile_revision: integer(data.profile_revision),
        preferences: decodePreferences(data.effective_preferences),
        notices: list(data.notices, text),
        items: list(data.items, (value) => {
          const item = object(value)
          return {
            listing: decodeDetail(item.listing),
            reasons: list(item.reasons, text),
          }
        }),
      }
    },
    {
      method: 'POST',
      json: { include_unknown_availability: unknownAvailability },
    },
  )
