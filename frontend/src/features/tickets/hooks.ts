import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import * as ticketApi from './api'
import type { TicketFilters } from './api'
import { agentsKey, referenceKey, ticketKeys } from './keys'
import { errorMessage } from '@/lib/api/client'
import type { TicketDetail } from '@/lib/api/types'

const POLL_MS = 1500
const POLL_WINDOW_MS = 30_000

export function useTickets(filters: TicketFilters) {
  return useInfiniteQuery({
    queryKey: ticketKeys.list(filters),
    queryFn: ({ pageParam }) => ticketApi.listTickets(filters, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  })
}

export function useTicket(id: string) {
  return useQuery({
    queryKey: ticketKeys.detail(id),
    queryFn: () => ticketApi.getTicket(id),
    // Poll while triage is running, but give up ~30s after creation so a stuck job
    // doesn't poll forever.
    refetchInterval: (query) => {
      const t = query.state.data
      if (!t || t.triage_status !== 'PENDING') return false
      const age = Date.now() - Date.parse(t.created_at)
      return age < POLL_WINDOW_MS ? POLL_MS : false
    },
  })
}

export function useEvents(id: string) {
  return useQuery({ queryKey: ticketKeys.events(id), queryFn: () => ticketApi.getEvents(id) })
}

export function useReference() {
  return useQuery({ queryKey: referenceKey, queryFn: ticketApi.getReference, staleTime: 300_000 })
}

export function useAgents(departmentId?: string) {
  return useQuery({
    queryKey: agentsKey(departmentId),
    queryFn: () => ticketApi.listAgents(departmentId),
  })
}

export function useCreateTicket() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ title, description }: { title: string; description: string }) =>
      ticketApi.createTicket(title, description),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ticketKeys.lists() }),
    onError: (e) => toast.error(errorMessage(e, 'Could not submit the ticket')),
  })
}

/** Shared optimistic patch of the detail query, rolled back on error with a toast. */
function useOptimisticDetail<V>(
  id: string,
  mutationFn: (v: V) => Promise<TicketDetail>,
  patch: (current: TicketDetail, v: V) => TicketDetail,
  successMsg?: string,
) {
  const qc = useQueryClient()
  const key = ticketKeys.detail(id)
  return useMutation({
    mutationFn,
    onMutate: async (v: V) => {
      await qc.cancelQueries({ queryKey: key })
      const prev = qc.getQueryData<TicketDetail>(key)
      if (prev) qc.setQueryData(key, patch(prev, v))
      return { prev }
    },
    onError: (e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(key, ctx.prev)
      toast.error(errorMessage(e))
    },
    onSuccess: (updated) => {
      qc.setQueryData(key, updated)
      if (successMsg) toast.success(successMsg)
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: ticketKeys.events(id) })
      void qc.invalidateQueries({ queryKey: ticketKeys.lists() })
    },
  })
}

export function useSetStatus(id: string) {
  return useOptimisticDetail<string>(
    id,
    (status) => ticketApi.setStatus(id, status),
    (t, status) => ({ ...t, status: status as TicketDetail['status'] }),
    'Status updated',
  )
}

export function useSetAssignee(id: string) {
  return useOptimisticDetail<{ assignee_id: string | null; reason: string; name: string | null }>(
    id,
    ({ assignee_id, reason }) => ticketApi.setAssignee(id, assignee_id, reason),
    (t, { assignee_id, name }) => ({
      ...t,
      assignee: assignee_id ? { id: assignee_id, full_name: name ?? '…', email: '' } : null,
    }),
    'Ticket reassigned',
  )
}

export function useReopen(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => ticketApi.reopenTicket(id),
    onSuccess: (t) => {
      qc.setQueryData(ticketKeys.detail(id), t)
      void qc.invalidateQueries({ queryKey: ticketKeys.lists() })
      void qc.invalidateQueries({ queryKey: ticketKeys.events(id) })
      toast.success('Ticket reopened')
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
}

export function useFeedback(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (helpful: boolean) => ticketApi.sendFeedback(id, helpful),
    onSuccess: (t) => {
      qc.setQueryData(ticketKeys.detail(id), t)
      void qc.invalidateQueries({ queryKey: ticketKeys.lists() })
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
}

export function useAddComment(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ body, is_internal }: { body: string; is_internal: boolean }) =>
      ticketApi.addComment(id, body, is_internal),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ticketKeys.events(id) })
      void qc.invalidateQueries({ queryKey: ticketKeys.detail(id) })
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
}
