import { Lock } from 'lucide-react'
import { cn } from '@/components/ui'
import { titleCase } from '@/lib/constants'
import { formatDateTime } from '@/lib/format'
import type { TicketEvent } from '@/lib/api/types'

function summarize(e: TicketEvent): string {
  const who = e.actor?.full_name ?? 'System'
  switch (e.type) {
    case 'CREATED':
      return `${who} created the ticket`
    case 'TRIAGED':
      return `Triaged as ${e.to_value ? titleCase(e.to_value) : 'done'}`
    case 'STATUS_CHANGED':
      return `${who} changed status ${e.from_value ? `from ${titleCase(e.from_value)} ` : ''}to ${titleCase(e.to_value ?? '')}`
    case 'ASSIGNED':
      return e.to_value ? `Assigned to ${e.to_value}` : `${who} unassigned the ticket`
    case 'REOPENED':
      return `${who} reopened the ticket`
    case 'FEEDBACK':
      return `${who} marked the answer ${e.to_value === 'helpful' ? 'helpful' : 'not helpful'}`
    default:
      return `${who} commented`
  }
}

export function Timeline({ events }: { events: TicketEvent[] }) {
  return (
    <ol className="space-y-4">
      {events.map((e) => {
        const isMessage = e.type === 'NOTE' || e.type === 'REPLY'
        return (
          <li key={e.id} className="text-sm">
            {isMessage ? (
              <div
                className={cn(
                  'rounded-lg border p-3',
                  e.is_internal
                    ? 'border-amber-300 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/40'
                    : 'border-border bg-card',
                )}
              >
                <div className="text-muted-foreground mb-1 flex items-center gap-2 text-xs">
                  <span className="text-foreground font-medium">
                    {e.actor?.full_name ?? 'System'}
                  </span>
                  {e.is_internal && (
                    <span className="inline-flex items-center gap-1 text-amber-700 dark:text-amber-400">
                      <Lock className="size-3" aria-hidden /> internal note
                    </span>
                  )}
                  <span className="ml-auto">{formatDateTime(e.created_at)}</span>
                </div>
                <p className="whitespace-pre-wrap">{e.body}</p>
              </div>
            ) : (
              <div className="text-muted-foreground flex gap-2">
                <span className="bg-border mt-1.5 size-1.5 shrink-0 rounded-full" aria-hidden />
                <span>{summarize(e)}</span>
                <span className="ml-auto text-xs whitespace-nowrap">
                  {formatDateTime(e.created_at)}
                </span>
              </div>
            )}
          </li>
        )
      })}
    </ol>
  )
}
