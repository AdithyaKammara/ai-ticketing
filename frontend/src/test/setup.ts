import '@testing-library/jest-dom/vitest'
import { configure } from '@testing-library/react'

// Pages are lazy-loaded; on a busy machine or CI runner the first chunk can take over the
// default 1 s, which made findBy* queries flaky.
configure({ asyncUtilTimeout: 5000 })

// React Router builds Requests with jsdom's AbortSignal, which Node's Request rejects.
// Tests never abort navigations, so drop the signal.
const NodeRequest = globalThis.Request
globalThis.Request = class extends NodeRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    const rest = { ...init }
    delete rest.signal
    super(input, rest)
  }
}
