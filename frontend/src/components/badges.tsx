import { AlertTriangle } from 'lucide-react'
import { Badge } from '@/components/ui'
import { SEVERITY_META, STATUS_META, TRIAGE_META } from '@/lib/constants'
import type { Severity, TicketStatus, TriageStatus } from '@/lib/api/types'

export function StatusBadge({ status }: { status: TicketStatus }) {
  const m = STATUS_META[status]
  return <Badge className={m.className}>{m.label}</Badge>
}

export function SeverityBadge({ severity }: { severity: Severity | null | undefined }) {
  if (!severity) return <span className="text-muted-foreground">—</span>
  const m = SEVERITY_META[severity]
  return <Badge className={m.className}>{m.label}</Badge>
}

export function TriageBadge({ status }: { status: TriageStatus }) {
  const m = TRIAGE_META[status]
  return <Badge className={m.className}>{m.label}</Badge>
}

export function OverdueBadge() {
  return (
    <Badge className="gap-1 bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200">
      <AlertTriangle className="size-3" aria-hidden />
      Overdue
    </Badge>
  )
}
