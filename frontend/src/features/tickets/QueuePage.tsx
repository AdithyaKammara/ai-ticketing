import { useSearchParams } from 'react-router-dom'
import { PageHeader } from '@/components/AppShell'
import { EmptyState, ErrorState } from '@/components/states'
import { Button, Input, Select, cn } from '@/components/ui'
import { SEVERITIES, SEVERITY_META, STATUSES, STATUS_META, CATEGORY_LABEL } from '@/lib/constants'
import { errorMessage } from '@/lib/api/client'
import { useMe } from '@/features/auth/authStore'
import type { TicketFilters } from './api'
import { useReference, useTickets } from './hooks'
import { TicketList, TicketListSkeleton } from './TicketList'

type Tab = 'me' | 'dept' | 'unassigned' | 'all'

const TABS: { id: Tab; label: string; admin?: boolean }[] = [
  { id: 'me', label: 'Assigned to me' },
  { id: 'dept', label: 'My department' },
  { id: 'unassigned', label: 'Unassigned', admin: true },
  { id: 'all', label: 'All', admin: true },
]

export default function QueuePage() {
  const user = useMe()
  const reference = useReference()
  const [params, setParams] = useSearchParams()
  const tab = (params.get('tab') as Tab | null) ?? 'me'

  const set = (key: string, value: string) => {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (value) next.set(key, value)
        else next.delete(key)
        return next
      },
      { replace: true },
    )
  }

  const scope: TicketFilters =
    tab === 'me'
      ? { assignee_id: user.id }
      : tab === 'dept'
        ? { department_id: user.department?.id ?? undefined }
        : tab === 'unassigned'
          ? { unassigned: true }
          : {}

  const one = (key: string) => {
    const v = params.get(key)
    return v ? [v] : undefined
  }
  const filters: TicketFilters = {
    ...scope,
    status: one('status'),
    severity: one('severity'),
    category: one('category'),
    q: params.get('q') ?? undefined,
    overdue: params.get('overdue') === '1' ? true : undefined,
    sort: (params.get('sort') as TicketFilters['sort']) ?? '-created_at',
  }

  const query = useTickets(filters)
  const items = query.data?.pages.flatMap((p) => p.items) ?? []
  const tabs = TABS.filter((t) => !t.admin || user.role === 'ADMIN')

  return (
    <div>
      <PageHeader title="Ticket queue" />

      <div className="border-border mb-4 flex flex-wrap gap-1 border-b">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => set('tab', t.id)}
            className={cn(
              'border-b-2 px-3 py-2 text-sm font-medium',
              tab === t.id
                ? 'border-primary text-foreground'
                : 'text-muted-foreground hover:text-foreground border-transparent',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <Input
          placeholder="Search title…"
          defaultValue={params.get('q') ?? ''}
          onChange={(e) => set('q', e.target.value)}
          aria-label="Search title"
        />
        <Select
          value={params.get('status') ?? ''}
          onChange={(e) => set('status', e.target.value)}
          aria-label="Status"
        >
          <option value="">Any status</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_META[s].label}
            </option>
          ))}
        </Select>
        <Select
          value={params.get('severity') ?? ''}
          onChange={(e) => set('severity', e.target.value)}
          aria-label="Severity"
        >
          <option value="">Any severity</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {SEVERITY_META[s].label}
            </option>
          ))}
        </Select>
        <Select
          value={params.get('category') ?? ''}
          onChange={(e) => set('category', e.target.value)}
          aria-label="Category"
        >
          <option value="">Any category</option>
          {reference.data?.categories.map((c) => (
            <option key={c.category} value={c.category}>
              {CATEGORY_LABEL(c.category)}
            </option>
          ))}
        </Select>
        <Select
          value={params.get('sort') ?? '-created_at'}
          onChange={(e) => set('sort', e.target.value)}
          aria-label="Sort"
        >
          <option value="-created_at">Newest</option>
          <option value="created_at">Oldest</option>
          <option value="due">Due soonest</option>
          <option value="severity">Severity</option>
        </Select>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={params.get('overdue') === '1'}
            onChange={(e) => set('overdue', e.target.checked ? '1' : '')}
          />
          Overdue only
        </label>
      </div>

      {query.isPending ? (
        <TicketListSkeleton />
      ) : query.isError ? (
        <ErrorState message={errorMessage(query.error)} onRetry={() => void query.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState title="No tickets match" hint="Try a different tab or clear the filters." />
      ) : (
        <>
          <TicketList items={items} />
          {query.hasNextPage && (
            <div className="mt-4 text-center">
              <Button
                variant="outline"
                loading={query.isFetchingNextPage}
                onClick={() => void query.fetchNextPage()}
              >
                Load more
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
