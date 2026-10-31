import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { PageHeader } from '@/components/AppShell'
import { ErrorState } from '@/components/states'
import { Card, Input, Skeleton } from '@/components/ui'
import { ApiRequestError, api, errorMessage } from '@/lib/api/client'
import { useMe } from '@/features/auth/authStore'

const pct = (v: number) => `${Math.round(v * 100)}%`
const iso = (d: Date) => d.toISOString().slice(0, 10)

function useAnalytics<T>(path: string, query: Record<string, string>, enabled = true) {
  return useQuery({
    queryKey: ['analytics', path, query],
    enabled,
    queryFn: async () => {
      // Paths are typed individually below; a loose call keeps this hook one function.
      const { data, error } = await api.GET(path as '/api/v1/analytics/summary', {
        params: { query: query as never },
      })
      if (error) throw new ApiRequestError(error)
      return data as T
    },
  })
}

export default function DashboardPage() {
  const user = useMe()
  const [params, setParams] = useSearchParams()
  const today = new Date()
  const from = params.get('from') ?? iso(new Date(today.getTime() - 30 * 86_400_000))
  const to = params.get('to') ?? iso(today)
  const range = { from, to }

  const summary = useAnalytics<{
    open_tickets: number
    resolved_this_period: number
    auto_resolution_rate: number
    reopen_rate: number
    median_first_response_minutes: number | null
    sla_breaches: number
  }>('/api/v1/analytics/summary', range)
  const volume = useAnalytics<{ day: string; created: number; resolved: number }[]>(
    '/api/v1/analytics/volume',
    range,
  )
  const byDept = useAnalytics<{ key: string; label: string; count: number }[]>(
    '/api/v1/analytics/breakdown',
    { ...range, by: 'department' },
  )
  const byCategory = useAnalytics<{ key: string; label: string; count: number }[]>(
    '/api/v1/analytics/breakdown',
    { ...range, by: 'category' },
  )
  const ai = useAnalytics<{
    triaged: number
    auto_resolved: number
    routed: number
    failed: number
    auto_resolution_rate: number
    reopen_rate: number
    helpful_rate: number | null
    confidence_histogram: { bucket: string; count: number }[]
  }>('/api/v1/analytics/ai-quality', range, user.role === 'ADMIN')

  const setDate = (key: 'from' | 'to', value: string) =>
    setParams((p) => {
      const next = new URLSearchParams(p)
      next.set(key, value)
      return next
    })

  if (summary.isError)
    return (
      <ErrorState message={errorMessage(summary.error)} onRetry={() => void summary.refetch()} />
    )

  const s = summary.data
  return (
    <div className="space-y-6">
      <PageHeader
        title={user.role === 'ADMIN' ? 'Dashboard' : `${user.department?.name ?? 'Team'} dashboard`}
        actions={
          <div className="flex items-center gap-2 text-sm">
            <Input
              type="date"
              aria-label="From"
              value={from}
              max={to}
              onChange={(e) => setDate('from', e.target.value)}
            />
            <span className="text-muted-foreground">to</span>
            <Input
              type="date"
              aria-label="To"
              value={to}
              min={from}
              onChange={(e) => setDate('to', e.target.value)}
            />
          </div>
        }
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Kpi label="Open tickets" value={s?.open_tickets} />
        <Kpi label="Resolved" value={s?.resolved_this_period} />
        <Kpi label="Auto-resolution rate" value={s && pct(s.auto_resolution_rate)} />
        <Kpi label="Reopen rate" value={s && pct(s.reopen_rate)} />
        <Kpi
          label="Median first response"
          value={
            s &&
            (s.median_first_response_minutes == null
              ? '—'
              : `${Math.round(s.median_first_response_minutes)} min`)
          }
        />
        <Kpi label="SLA breaches" value={s?.sla_breaches} danger={!!s?.sla_breaches} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Tickets per day" loading={volume.isPending}>
          <LineChart data={volume.data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="day"
              tickFormatter={(d: string) => d.slice(5)}
              stroke="var(--muted-foreground)"
              fontSize={12}
            />
            <YAxis allowDecimals={false} stroke="var(--muted-foreground)" fontSize={12} />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend />
            <Line
              type="monotone"
              dataKey="created"
              stroke="var(--primary)"
              dot={false}
              name="Created"
            />
            <Line
              type="monotone"
              dataKey="resolved"
              stroke="var(--success)"
              dot={false}
              name="Resolved"
            />
          </LineChart>
        </ChartCard>

        <ChartCard title="Tickets by department" loading={byDept.isPending}>
          <BarChart data={byDept.data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="label" stroke="var(--muted-foreground)" fontSize={12} />
            <YAxis allowDecimals={false} stroke="var(--muted-foreground)" fontSize={12} />
            <Tooltip contentStyle={tooltipStyle} />
            <Bar dataKey="count" fill="var(--primary)" name="Tickets" />
          </BarChart>
        </ChartCard>

        <ChartCard title="Top categories" loading={byCategory.isPending}>
          <BarChart data={byCategory.data} layout="vertical" margin={{ left: 40 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              type="number"
              allowDecimals={false}
              stroke="var(--muted-foreground)"
              fontSize={12}
            />
            <YAxis
              type="category"
              dataKey="label"
              interval={0}
              stroke="var(--muted-foreground)"
              fontSize={11}
              width={110}
            />
            <Tooltip contentStyle={tooltipStyle} />
            <Bar dataKey="count" fill="var(--primary)" name="Tickets" />
          </BarChart>
        </ChartCard>

        {user.role === 'ADMIN' && (
          <ChartCard title="AI confidence distribution" loading={ai.isPending}>
            <BarChart data={ai.data?.confidence_histogram}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="bucket" stroke="var(--muted-foreground)" fontSize={12} />
              <YAxis allowDecimals={false} stroke="var(--muted-foreground)" fontSize={12} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="count" fill="var(--primary)" name="Tickets" />
            </BarChart>
          </ChartCard>
        )}
      </div>

      {user.role === 'ADMIN' && ai.data && (
        <Card className="p-5">
          <h2 className="mb-3 text-sm font-semibold">AI quality</h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
            <Kpi label="Triaged" value={ai.data.triaged} />
            <Kpi label="Auto-resolved" value={ai.data.auto_resolved} />
            <Kpi label="Routed" value={ai.data.routed} />
            <Kpi label="Failed" value={ai.data.failed} danger={ai.data.failed > 0} />
            <Kpi label="Auto-resolve rate" value={pct(ai.data.auto_resolution_rate)} />
            <Kpi label="Reopen rate" value={pct(ai.data.reopen_rate)} />
            <Kpi
              label="Helpful votes"
              value={ai.data.helpful_rate == null ? '—' : pct(ai.data.helpful_rate)}
            />
          </div>
        </Card>
      )}
    </div>
  )
}

const tooltipStyle = {
  background: 'var(--card)',
  border: '1px solid var(--border)',
  color: 'var(--foreground)',
  borderRadius: 6,
}

function Kpi({ label, value, danger }: { label: string; value: ReactNode; danger?: boolean }) {
  return (
    <Card className="p-4">
      <p className="text-muted-foreground text-xs">{label}</p>
      {value === undefined ? (
        <Skeleton className="mt-2 h-7 w-12" />
      ) : (
        <p className={`mt-1 text-2xl font-semibold tabular-nums ${danger ? 'text-danger' : ''}`}>
          {value}
        </p>
      )}
    </Card>
  )
}

function ChartCard({
  title,
  loading,
  children,
}: {
  title: string
  loading: boolean
  children: ReactNode
}) {
  return (
    <Card className="p-4">
      <h2 className="mb-3 text-sm font-semibold">{title}</h2>
      <div className="h-64">
        {loading ? (
          <Skeleton className="h-full w-full" />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            {children as React.ReactElement}
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  )
}
