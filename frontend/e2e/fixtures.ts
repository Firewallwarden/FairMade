import { test as base } from '@playwright/test'
import { auditBrowserRequests } from './helpers'

export const test = base.extend({
  page: async ({ page }, runFixture) => {
    auditBrowserRequests(page)
    await runFixture(page)
  },
})
export { expect, request } from '@playwright/test'
