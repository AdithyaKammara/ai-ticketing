import { Link } from 'react-router-dom'
import { OverdueBadge, SeverityBadge, StatusBadge } from '@/components/badges'
import { Card, Skeleton } from '@/components/ui'
import { CATEGORY_LABEL, DONE_STATUSES } from '@/lib/constants'
import { countdown, relativeTime } from '@/lib/format'
import type { TicketSummary } from '@/lib/api/types'

function Row({ ticket }: { ticket: TicketSummary }) {
  const due = DONE_STATUSES.includes(ticket.status) ? null : countdown(ticket.resolve_due_at)
  return (
    <Link
      to={`/tickets/${ticket.id}`}
      className="border-border bg-card hover:border-primary focus-visible:ring-primary block rounded-lg border p-4 transition focus-visible:ring-2 focus-visible:outline-none"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted-foreground font-mono text-xs">{ticket.number}</span>
        <StatusBadge status={ticket.status} />
        <SeverityBadge severity={ticket.severity} />
        {ticket.is_overdue && <OverdueBadge />}
        <span className="text-muted-foreground ml-auto text-xs">
          {relativeTime(ticket.created_at)}
        </span>
      </div>
      <p className="mt-2 font-medium">{ticket.title}</p>
      <div className="text-muted-foreground mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {ticket.category && <span>{CATEGORY_LABEL(ticket.category)}</span>}
        <span>{ticket.assignee ? `Assigned to ${ticket.assignee.full_name}` : 'Unassigned'}</span>
        {due && (
          <span className={due.overdue ? 'text-danger' : undefined}>
            {due.overdue ? due.label : `Due in ${due.label}`}
          </span>
        )}
      </div>
    </Link>
  )
}

export function TicketList({ items }: { items: TicketSummary[] }) {
  return (
    <div className="space-y-3">
      {items.map((t) => (
        <Row key={t.id} ticket={t} />
      ))}
    </div>
  )
}

export function TicketListSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 5 }, (_, i) => (
        <Card key={i} className="p-4">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="mt-3 h-5 w-2/3" />
        </Card>
      ))}
    </div>
  )
}
