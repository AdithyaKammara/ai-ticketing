import type { TicketFilters } from './api'

export const ticketKeys = {
  all: ['tickets'] as const,
  lists: () => [...ticketKeys.all, 'list'] as const,
  list: (filters: TicketFilters) => [...ticketKeys.lists(), filters] as const,
  detail: (id: string) => [...ticketKeys.all, 'detail', id] as const,
  events: (id: string) => [...ticketKeys.all, 'events', id] as const,
}

export const referenceKey = ['reference'] as const
export const agentsKey = (deptId?: string) => ['users', 'agents', deptId ?? 'all'] as const
