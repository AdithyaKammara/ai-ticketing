import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useAuth } from '@/features/auth/authStore'
import { api } from '@/lib/api/client'
import { ME, mockApi, renderAt, signIn } from '@/test/utils'

afterEach(() => {
  vi.unstubAllGlobals()
  useAuth.setState({ user: null, accessToken: null, ready: false })
})

const emptyPage = { items: [], next_cursor: null }

describe('RequireAuth', () => {
  it('sends signed-out visitors to the login page', async () => {
    signIn(null)
    mockApi()
    const { router } = renderAt('/queue')

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
  })

  it('sends a requester away from agent-only pages to their own home', async () => {
    signIn(ME.REQUESTER)
    mockApi(({ path }) => (path.startsWith('/api/v1/tickets') ? { body: emptyPage } : undefined))
    const { router } = renderAt('/queue')

    expect(await screen.findByRole('heading', { name: 'My tickets' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/my-tickets')
  })

  it('lands each role on its home page from /', async () => {
    signIn(ME.AGENT)
    mockApi(() => ({ body: emptyPage }))
    const { router } = renderAt('/')

    await waitFor(() => expect(router.state.location.pathname).toBe('/queue'))
  })
})

describe('LoginPage', () => {
  it('validates the form before calling the API', async () => {
    signIn(null)
    const calls = mockApi()
    renderAt('/login')

    await userEvent.click(await screen.findByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Enter a valid email')).toBeInTheDocument()
    expect(screen.getByText('Enter your password')).toBeInTheDocument()
    expect(calls).toHaveLength(0)
  })

  it('signs in with a demo account and goes to that role’s home', async () => {
    signIn(null)
    const calls = mockApi(
      ({ path }) =>
        path === '/api/v1/auth/login'
          ? { body: { access_token: 't', token_type: 'bearer', expires_in: 900, user: ME.ADMIN } }
          : undefined,
      () => ({ body: [] }),
    )
    const { router } = renderAt('/login')

    await userEvent.click(await screen.findByRole('button', { name: 'Admin' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/dashboard'))
    expect(calls[0]?.body).toEqual({ email: 'admin@acme.example', password: 'ticketing-demo' })
  })

  it('shows the server error when sign-in fails', async () => {
    signIn(null)
    mockApi(() => ({
      status: 401,
      body: {
        error: {
          code: 'INVALID_CREDENTIALS',
          message: 'Email or password is incorrect',
          details: {},
        },
      },
    }))
    renderAt('/login')

    await userEvent.type(await screen.findByLabelText('Email'), 'x@acme.example')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Email or password is incorrect')).toBeInTheDocument()
  })
})

describe('API client', () => {
  it('refreshes once on 401 and retries the original request with its body', async () => {
    signIn(ME.REQUESTER)
    let created = 0
    const calls = mockApi(({ method, path }) => {
      if (path === '/api/v1/auth/refresh')
        return {
          body: {
            access_token: 'fresh',
            token_type: 'bearer',
            expires_in: 900,
            user: ME.REQUESTER,
          },
        }
      if (method === 'POST' && path === '/api/v1/tickets') {
        created += 1
        return created === 1
          ? {
              status: 401,
              body: { error: { code: 'UNAUTHENTICATED', message: 'expired', details: {} } },
            }
          : {
              status: 201,
              body: {
                id: 't1',
                number: 'TKT-1',
                status: 'TRIAGING',
                triage_status: 'PENDING',
                created_at: '2026-10-31T09:00:00Z',
              },
            }
      }
      return undefined
    })

    const result = await api.POST('/api/v1/tickets', {
      body: { title: 'Laptop broken', description: 'It will not turn on at all today.' },
    })

    expect(result.error).toBeUndefined()
    expect(result.data?.number).toBe('TKT-1')
    expect(useAuth.getState().accessToken).toBe('fresh')
    const retried = calls.filter((c) => c.path === '/api/v1/tickets')
    expect(retried).toHaveLength(2)
    expect(retried[1]?.body).toEqual(retried[0]?.body)
  })
})
