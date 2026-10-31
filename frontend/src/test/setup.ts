import '@testing-library/jest-dom/vitest'

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
