import type { Category, Severity, TicketStatus, TriageStatus } from '@/lib/api/types'

// One source for status/severity labels and colours. Chips use colour AND text (never
// colour alone), so they stay legible for colour-blind users and in both themes.
type Meta = { label: string; className: string }

export const STATUS_META: Record<TicketStatus, Meta> = {
  TRIAGING: {
    label: 'Triaging',
    className: 'bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-200',
  },
  NEW: { label: 'New', className: 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200' },
  IN_PROGRESS: {
    label: 'In progress',
    className: 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200',
  },
  WAITING_ON_REQUESTER: {
    label: 'Waiting on requester',
    className: 'bg-orange-100 text-orange-900 dark:bg-orange-950 dark:text-orange-200',
  },
  RESOLVED: {
    label: 'Resolved',
    className: 'bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200',
  },
  AUTO_RESOLVED: {
    label: 'Auto-resolved',
    className: 'bg-teal-100 text-teal-800 dark:bg-teal-950 dark:text-teal-200',
  },
  CLOSED: {
    label: 'Closed',
    className: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  },
}

export const SEVERITY_META: Record<Severity, Meta> = {
  CRITICAL: {
    label: 'Critical',
    className: 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200',
  },
  HIGH: {
    label: 'High',
    className: 'bg-orange-100 text-orange-900 dark:bg-orange-950 dark:text-orange-200',
  },
  MEDIUM: {
    label: 'Medium',
    className: 'bg-yellow-100 text-yellow-900 dark:bg-yellow-950 dark:text-yellow-200',
  },
  LOW: {
    label: 'Low',
    className: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  },
}

export const TRIAGE_META: Record<TriageStatus, Meta> = {
  PENDING: {
    label: 'Triage pending',
    className: 'bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-200',
  },
  DONE: {
    label: 'Triaged',
    className: 'bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200',
  },
  FAILED: {
    label: 'Needs review',
    className: 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200',
  },
  SKIPPED: {
    label: 'Not triaged',
    className: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  },
}

export function titleCase(value: string): string {
  return value
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export const CATEGORY_LABEL = (c: Category): string => titleCase(c)

export const STATUSES = Object.keys(STATUS_META) as TicketStatus[]
// Finished tickets have no SLA left to count down.
export const DONE_STATUSES: TicketStatus[] = ['RESOLVED', 'AUTO_RESOLVED', 'CLOSED']
export const SEVERITIES = Object.keys(SEVERITY_META) as Severity[]

// Manual transitions an agent/admin may make — mirrors backend app/services/workflow.py so
// the status dropdown only offers legal moves. The server still enforces it.
export const MANUAL_TRANSITIONS: Record<TicketStatus, TicketStatus[]> = {
  TRIAGING: [],
  NEW: ['IN_PROGRESS', 'WAITING_ON_REQUESTER', 'RESOLVED', 'CLOSED'],
  IN_PROGRESS: ['WAITING_ON_REQUESTER', 'RESOLVED'],
  WAITING_ON_REQUESTER: ['IN_PROGRESS', 'RESOLVED'],
  RESOLVED: ['CLOSED'],
  AUTO_RESOLVED: ['CLOSED'],
  CLOSED: [],
}
