import { Loader2, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { OverdueBadge, SeverityBadge, StatusBadge, TriageBadge } from '@/components/badges'
import { PageHeader } from '@/components/AppShell'
import { ErrorState } from '@/components/states'
import { Button, Card, Field, Select, Spinner, Textarea } from '@/components/ui'
import { CATEGORY_LABEL, DONE_STATUSES, MANUAL_TRANSITIONS, STATUS_META } from '@/lib/constants'
import { countdown, formatDateTime } from '@/lib/format'
import { errorMessage } from '@/lib/api/client'
import { useMe } from '@/features/auth/authStore'
import type { Me, TicketDetail } from '@/lib/api/types'
import {
  useAddComment,
  useAgents,
  useEvents,
  useFeedback,
  useReopen,
  useSetAssignee,
  useSetStatus,
  useTicket,
} from './hooks'
import { Timeline } from './Timeline'

function canManage(user: Me, t: TicketDetail): boolean {
  if (user.role === 'ADMIN') return true
  if (user.role !== 'AGENT') return false
  return t.assignee?.id === user.id || (!!t.department && t.department.id === user.department?.id)
}

export default function TicketDetailPage() {
  const { id = '' } = useParams()
  const user = useMe()
  const ticket = useTicket(id)
  const events = useEvents(id, ticket.data?.updated_at)

  if (ticket.isPending) return <Spinner label="Loading ticket" />
  if (ticket.isError)
    return <ErrorState message={errorMessage(ticket.error)} onRetry={() => void ticket.refetch()} />

  const t = ticket.data
  const due = DONE_STATUSES.includes(t.status) ? null : countdown(t.resolve_due_at)
  const manage = canManage(user, t)
  const isRequester = t.requester.id === user.id

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title={t.number}
        actions={
          <div className="flex items-center gap-2">
            <StatusBadge status={t.status} />
            <SeverityBadge severity={t.severity} />
            {t.triage_status !== 'DONE' && <TriageBadge status={t.triage_status} />}
            {t.is_overdue && <OverdueBadge />}
          </div>
        }
      />

      <Card className="space-y-3 p-5">
        <h2 className="text-lg font-semibold">{t.title}</h2>
        <p className="text-muted-foreground text-sm whitespace-pre-wrap">{t.description}</p>
        <div className="text-muted-foreground flex flex-wrap gap-x-4 gap-y-1 text-xs">
          <span>From {t.requester.full_name}</span>
          <span>{formatDateTime(t.created_at)}</span>
          <span>{t.assignee ? `Assigned to ${t.assignee.full_name}` : 'Unassigned'}</span>
          {due && (
            <span className={due.overdue ? 'text-danger' : undefined}>
              {due.overdue ? due.label : `Due in ${due.label}`}
            </span>
          )}
        </div>
      </Card>

      {t.triage_status === 'PENDING' && (
        <Card className="text-muted-foreground mt-4 flex items-center gap-3 p-4 text-sm">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          Triaging your ticket… this usually takes a few seconds.
        </Card>
      )}

      {t.ai_summary && (
        <Card className="mt-4 space-y-3 p-5">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Sparkles className="text-primary size-4" aria-hidden /> AI triage
          </div>
          <p className="text-sm">{t.ai_summary}</p>
          <div className="text-muted-foreground flex flex-wrap gap-4 text-xs">
            {t.category && <span>Category: {CATEGORY_LABEL(t.category)}</span>}
            {t.ai_confidence != null && (
              <span className="flex items-center gap-2">
                Confidence
                <span className="bg-muted inline-block h-2 w-24 overflow-hidden rounded-full">
                  <span
                    className="bg-primary block h-full"
                    style={{ width: `${t.ai_confidence}%` }}
                  />
                </span>
                {t.ai_confidence}%
              </span>
            )}
          </div>
        </Card>
      )}

      {t.status === 'AUTO_RESOLVED' && t.auto_response && (
        <Card className="mt-4 space-y-3 border-teal-300 p-5 dark:border-teal-900">
          <p className="text-sm font-medium">Suggested answer</p>
          <p className="text-sm whitespace-pre-wrap">{t.auto_response}</p>
          {isRequester && <AutoResolvedActions id={id} feedbackGiven={t.feedback_given} />}
        </Card>
      )}

      {isRequester &&
        (t.status === 'RESOLVED' || (t.status === 'AUTO_RESOLVED' && t.feedback_given)) && (
          <ReopenButton id={id} />
        )}

      {manage && <ManagePanel ticket={t} />}

      <section className="mt-6">
        <h3 className="mb-3 text-sm font-semibold">Activity</h3>
        {events.isPending ? (
          <Spinner label="Loading activity" />
        ) : events.isError ? (
          <ErrorState message={errorMessage(events.error)} onRetry={() => void events.refetch()} />
        ) : (
          <Timeline events={events.data} />
        )}
        {t.status !== 'CLOSED' && <Composer id={id} canNote={manage} />}
      </section>
    </div>
  )
}

function AutoResolvedActions({ id, feedbackGiven }: { id: string; feedbackGiven: boolean }) {
  const feedback = useFeedback(id)
  if (feedbackGiven)
    return <p className="text-muted-foreground text-sm">Thanks for the feedback.</p>
  return (
    <div className="flex items-center gap-2">
      <span className="text-sm">Did this solve your problem?</span>
      <Button size="sm" onClick={() => feedback.mutate(true)} loading={feedback.isPending}>
        Yes
      </Button>
      <Button size="sm" variant="outline" onClick={() => feedback.mutate(false)}>
        No, reopen
      </Button>
    </div>
  )
}

function ReopenButton({ id }: { id: string }) {
  const reopen = useReopen(id)
  return (
    <div className="mt-4">
      <Button variant="outline" onClick={() => reopen.mutate()} loading={reopen.isPending}>
        Reopen ticket
      </Button>
    </div>
  )
}

function ManagePanel({ ticket }: { ticket: TicketDetail }) {
  const setStatus = useSetStatus(ticket.id)
  const setAssignee = useSetAssignee(ticket.id)
  const agents = useAgents(ticket.department?.id)
  const [reason, setReason] = useState('')
  const [assignee, setAssigneeId] = useState(ticket.assignee?.id ?? '')
  const nextStatuses = MANUAL_TRANSITIONS[ticket.status]

  return (
    <Card className="mt-4 grid gap-4 p-5 sm:grid-cols-2">
      <Field label="Status" htmlFor="ticket-status">
        <Select
          id="ticket-status"
          value=""
          disabled={nextStatuses.length === 0 || setStatus.isPending}
          onChange={(e) => e.target.value && setStatus.mutate(e.target.value)}
        >
          <option value="">{nextStatuses.length ? 'Move to…' : 'No moves available'}</option>
          {nextStatuses.map((s) => (
            <option key={s} value={s}>
              {STATUS_META[s].label}
            </option>
          ))}
        </Select>
      </Field>

      <Field label="Assignee" htmlFor="ticket-assignee">
        <div className="space-y-2">
          <Select
            id="ticket-assignee"
            value={assignee}
            onChange={(e) => setAssigneeId(e.target.value)}
          >
            <option value="">Unassigned</option>
            {agents.data?.map((a) => (
              <option key={a.id} value={a.id}>
                {a.full_name} ({a.open_tickets} open)
              </option>
            ))}
          </Select>
          <input
            className="border-border bg-card w-full rounded-md border px-3 py-2 text-sm"
            placeholder="Reason for reassigning"
            aria-label="Reason for reassigning"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <Button
            size="sm"
            variant="outline"
            disabled={reason.trim().length < 3}
            loading={setAssignee.isPending}
            onClick={() =>
              setAssignee.mutate({
                assignee_id: assignee || null,
                reason: reason.trim(),
                name: agents.data?.find((a) => a.id === assignee)?.full_name ?? null,
              })
            }
          >
            Apply assignee
          </Button>
        </div>
      </Field>
    </Card>
  )
}

function Composer({ id, canNote }: { id: string; canNote: boolean }) {
  const add = useAddComment(id)
  const [body, setBody] = useState('')
  const [internal, setInternal] = useState(false)

  const send = () => {
    if (!body.trim()) return
    add.mutate({ body: body.trim(), is_internal: internal }, { onSuccess: () => setBody('') })
  }

  return (
    <div className="mt-4 space-y-2">
      <Textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder={internal ? 'Internal note (not shown to the requester)' : 'Write a reply…'}
        aria-label={internal ? 'Internal note' : 'Reply'}
        rows={3}
      />
      <div className="flex items-center gap-3">
        <Button size="sm" onClick={send} loading={add.isPending} disabled={!body.trim()}>
          {internal ? 'Add note' : 'Send reply'}
        </Button>
        {canNote && (
          <label className="text-muted-foreground flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={internal}
              onChange={(e) => setInternal(e.target.checked)}
            />
            Internal note
          </label>
        )}
      </div>
    </div>
  )
}
