import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { Toaster } from 'sonner'
import { vi } from 'vitest'
import { routes } from '@/app/router'
import { useAuth } from '@/features/auth/authStore'
import type { Me } from '@/lib/api/types'

export const ME: Record<'REQUESTER' | 'AGENT' | 'ADMIN', Me> = {
  REQUESTER: {
    id: 'u-req',
    email: 'requester@acme.example',
    full_name: 'Priya Sharma',
    role: 'REQUESTER',
    department: null,
    availability: 'AVAILABLE',
    skills: [],
  },
  AGENT: {
    id: 'u-agent',
    email: 'agent@acme.example',
    full_name: 'Ravi Kumar',
    role: 'AGENT',
    department: { id: 'd-eng', name: 'Engineering', slug: 'engineering' },
    availability: 'AVAILABLE',
    skills: [],
  },
  ADMIN: {
    id: 'u-admin',
    email: 'admin@acme.example',
    full_name: 'Meena Iyer',
    role: 'ADMIN',
    department: null,
    availability: 'AVAILABLE',
    skills: [],
  },
}

type Handler = (req: {
  method: string
  path: string
  body: unknown
}) => { status?: number; body?: unknown } | undefined

/** Stub `fetch`: the first handler that returns a response wins; unmatched calls 404. */
export function mockApi(...handlers: Handler[]) {
  const calls: { method: string; path: string; body: unknown }[] = []
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    // Duck-type: a cloned Request is not an instance of the setup.ts Request shim.
    const req =
      typeof input === 'object' && 'url' in input
        ? input
        : new Request(new URL(String(input), location.origin), init)
    const text = await req.clone().text()
    const call = {
      method: init?.method ?? req.method,
      path: new URL(req.url).pathname + new URL(req.url).search,
      body: text ? (JSON.parse(text) as unknown) : undefined,
    }
    calls.push(call)
    for (const h of handlers) {
      const res = h(call)
      if (res)
        return new Response(res.body === undefined ? null : JSON.stringify(res.body), {
          status: res.status ?? 200,
          headers: { 'content-type': 'application/json' },
        })
    }
    return new Response(
      JSON.stringify({ error: { code: 'NOT_FOUND', message: 'unmocked', details: {} } }),
      {
        status: 404,
        headers: { 'content-type': 'application/json' },
      },
    )
  })
  vi.stubGlobal('fetch', fn)
  return calls
}

export function signIn(user: Me | null) {
  useAuth.setState({ user, accessToken: user ? 'token' : null, ready: true })
}

export function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={router} />
      <Toaster />
    </QueryClientProvider>,
  )
  return { router, qc }
}
