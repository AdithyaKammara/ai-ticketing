import { api, unwrap } from '@/lib/api/client'
import type { TicketDetail } from '@/lib/api/types'

export interface TicketFilters {
  status?: string[]
  severity?: string[]
  category?: string[]
  department_id?: string
  assignee_id?: string
  unassigned?: boolean
  requester_id?: string
  q?: string
  overdue?: boolean
  sort?: 'created_at' | '-created_at' | 'due' | 'severity'
}

// Drop empty strings and empty arrays so they don't become `?q=` noise in the URL.
function clean(f: TicketFilters): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(f).filter(
      ([, v]) => v !== undefined && v !== '' && !(Array.isArray(v) && v.length === 0),
    ),
  )
}

const path = (id: string) => ({ params: { path: { ticket_id: id } } })

export const listTickets = async (filters: TicketFilters, cursor: string | null) =>
  unwrap(
    await api.GET('/api/v1/tickets', {
      params: { query: { ...clean(filters), limit: 25, cursor: cursor ?? undefined } },
    }),
  )

export const getTicket = async (id: string) =>
  unwrap(await api.GET('/api/v1/tickets/{ticket_id}', path(id)))

export const getEvents = async (id: string) =>
  unwrap(await api.GET('/api/v1/tickets/{ticket_id}/events', path(id)))

export const createTicket = async (title: string, description: string) =>
  unwrap(await api.POST('/api/v1/tickets', { body: { title, description } }))

export const setStatus = async (id: string, status: string) =>
  unwrap(
    await api.PATCH('/api/v1/tickets/{ticket_id}/status', {
      ...path(id),
      body: { status: status as TicketDetail['status'] },
    }),
  )

export const setAssignee = async (id: string, assignee_id: string | null, reason: string) =>
  unwrap(
    await api.PATCH('/api/v1/tickets/{ticket_id}/assignee', {
      ...path(id),
      body: { assignee_id, reason },
    }),
  )

export const reopenTicket = async (id: string) =>
  unwrap(await api.POST('/api/v1/tickets/{ticket_id}/reopen', path(id)))

export const sendFeedback = async (id: string, helpful: boolean) =>
  unwrap(await api.POST('/api/v1/tickets/{ticket_id}/feedback', { ...path(id), body: { helpful } }))

export const addComment = async (id: string, body: string, is_internal: boolean) =>
  unwrap(
    await api.POST('/api/v1/tickets/{ticket_id}/comments', {
      ...path(id),
      body: { body, is_internal },
    }),
  )

export const listAgents = async (departmentId?: string) =>
  unwrap(
    await api.GET('/api/v1/users', {
      params: { query: { role: 'AGENT', department_id: departmentId } },
    }),
  )

export async function getReference() {
  const [departments, skills, categories] = await Promise.all([
    api.GET('/api/v1/departments', {}),
    api.GET('/api/v1/skills', {}),
    api.GET('/api/v1/categories', {}),
  ])
  return {
    departments: unwrap(departments),
    skills: unwrap(skills),
    categories: unwrap(categories),
  }
}
