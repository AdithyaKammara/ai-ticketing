import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useAuth } from '@/features/auth/authStore'
import { countdown } from '@/lib/format'
import type { TicketDetail } from '@/lib/api/types'
import { ME, mockApi, renderAt, signIn } from '@/test/utils'

afterEach(() => {
  vi.unstubAllGlobals()
  useAuth.setState({ user: null, accessToken: null, ready: false })
})

const brief = (u: typeof ME.AGENT) => ({ id: u.id, full_name: u.full_name, email: u.email })

function ticket(overrides: Partial<TicketDetail> = {}): TicketDetail {
  return {
    id: 't1',
    number: 'TKT-1042',
    title: 'Checkout page throws 500',
    description: 'Customers get a 500 error on Pay.',
    status: 'NEW',
    triage_status: 'DONE',
    category: 'BUG',
    severity: 'HIGH',
    sentiment: 'FRUSTRATED',
    department: ME.AGENT.department,
    requester: brief(ME.REQUESTER),
    assignee: brief(ME.AGENT),
    ai_summary: 'Checkout returns 500 since the release.',
    ai_confidence: 91,
    auto_response: null,
    first_response_due_at: null,
    resolve_due_at: null,
    first_responded_at: null,
    resolved_at: null,
    closed_at: null,
    created_at: '2026-10-31T09:00:00Z',
    updated_at: '2026-10-31T09:00:00Z',
    is_overdue: false,
    feedback_given: false,
    ...overrides,
  }
}

describe('TicketDetailPage', () => {
  it('rolls an optimistic status change back and shows the error', async () => {
    signIn(ME.AGENT)
    mockApi(({ method, path }) => {
      if (path === '/api/v1/tickets/t1' && method === 'GET') return { body: ticket() }
      if (path === '/api/v1/tickets/t1/events') return { body: [] }
      if (path.startsWith('/api/v1/users')) return { body: [] }
      if (path === '/api/v1/tickets/t1/status')
        return {
          status: 409,
          body: {
            error: {
              code: 'INVALID_TRANSITION',
              message: 'Cannot move NEW to RESOLVED',
              details: {},
            },
          },
        }
      return undefined
    })
    renderAt('/tickets/t1')

    const select = await screen.findByLabelText('Status')
    await userEvent.selectOptions(select, 'RESOLVED')

    expect(await screen.findByText('Cannot move NEW to RESOLVED')).toBeInTheDocument()
    await waitFor(() => expect(screen.getAllByText('New').length).toBeGreaterThan(0))
    // The status badge (a span) is back to New; 'Resolved' only remains as a dropdown option.
    expect(screen.queryByText('Resolved', { selector: 'span' })).not.toBeInTheDocument()
  })

  it('hides confidence, internal-note and status controls from the requester', async () => {
    signIn(ME.REQUESTER)
    mockApi(({ path }) => {
      if (path === '/api/v1/tickets/t1')
        return {
          body: ticket({ requester: brief(ME.REQUESTER), ai_confidence: null }),
        }
      if (path === '/api/v1/tickets/t1/events') return { body: [] }
      return undefined
    })
    renderAt('/tickets/t1')

    expect(await screen.findByText('Checkout page throws 500')).toBeInTheDocument()
    expect(screen.queryByText(/Confidence/)).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Status')).not.toBeInTheDocument()
    expect(screen.queryByText('Internal note')).not.toBeInTheDocument()
  })

  it('lets the requester say an automatic answer did not help', async () => {
    signIn(ME.REQUESTER)
    const auto = ticket({
      status: 'AUTO_RESOLVED',
      auto_response: 'Use the self-service reset link.',
      requester: brief(ME.REQUESTER),
      assignee: null,
    })
    const calls = mockApi(({ method, path }) => {
      if (path === '/api/v1/tickets/t1/feedback')
        return { body: { ...auto, status: 'NEW', feedback_given: true } }
      if (path === '/api/v1/tickets/t1' && method === 'GET') return { body: auto }
      if (path === '/api/v1/tickets/t1/events') return { body: [] }
      return undefined
    })
    renderAt('/tickets/t1')

    await userEvent.click(await screen.findByRole('button', { name: 'No, reopen' }))

    await waitFor(() =>
      expect(calls.some((c) => c.path === '/api/v1/tickets/t1/feedback')).toBe(true),
    )
    expect(calls.find((c) => c.path === '/api/v1/tickets/t1/feedback')?.body).toEqual({
      helpful: false,
    })
  })
})

describe('NewTicketPage', () => {
  it('submits and opens the new ticket', async () => {
    signIn(ME.REQUESTER)
    mockApi(({ method, path }) => {
      if (method === 'POST' && path === '/api/v1/tickets')
        return {
          status: 201,
          body: {
            id: 't9',
            number: 'TKT-9',
            status: 'TRIAGING',
            triage_status: 'PENDING',
            created_at: new Date().toISOString(),
          },
        }
      if (path === '/api/v1/tickets/t9')
        return { body: ticket({ id: 't9', status: 'TRIAGING', triage_status: 'PENDING' }) }
      if (path === '/api/v1/tickets/t9/events') return { body: [] }
      return undefined
    })
    const { router } = renderAt('/tickets/new')

    await userEvent.type(await screen.findByLabelText('Title'), 'Laptop will not boot')
    await userEvent.type(
      screen.getByLabelText('Description'),
      'Black screen after the logo since this morning.',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Submit ticket' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/tickets/t9'))
    expect(await screen.findByText(/Triaging your ticket/)).toBeInTheDocument()
  })
})

describe('countdown', () => {
  it('labels time left and time overdue', () => {
    const inTwoHours = new Date(Date.now() + 2 * 3_600_000 + 60_000).toISOString()
    const yesterday = new Date(Date.now() - 26 * 3_600_000).toISOString()

    expect(countdown(inTwoHours)).toEqual({ label: '2h 1m', overdue: false })
    expect(countdown(yesterday)).toEqual({ label: '1d 2h overdue', overdue: true })
    expect(countdown(null)).toBeNull()
  })
})
