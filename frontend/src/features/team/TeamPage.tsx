import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'
import { PageHeader } from '@/components/AppShell'
import { EmptyState, ErrorState } from '@/components/states'
import { Badge, Button, Card, Dialog, Field, Input, Select, Spinner } from '@/components/ui'
import { ApiRequestError, api, errorMessage } from '@/lib/api/client'
import { titleCase } from '@/lib/constants'
import type { Availability, Role, UserOut } from '@/lib/api/types'
import { useMe } from '@/features/auth/authStore'
import { useReference } from '@/features/tickets/hooks'

const usersKey = ['users', 'directory'] as const

type Draft = {
  full_name: string
  email: string
  password: string
  role: Role
  department_id: string
  availability: Availability
  skills: string
}

const emptyDraft: Draft = {
  full_name: '',
  email: '',
  password: '',
  role: 'AGENT',
  department_id: '',
  availability: 'AVAILABLE',
  skills: '',
}

export default function TeamPage() {
  const me = useMe()
  const isAdmin = me.role === 'ADMIN'
  const qc = useQueryClient()
  const [editing, setEditing] = useState<UserOut | 'new' | null>(null)

  const users = useQuery({
    queryKey: usersKey,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/v1/users', {})
      if (error) throw new ApiRequestError(error)
      return data.filter((u) => u.role !== 'REQUESTER')
    },
  })

  const deactivate = useMutation({
    mutationFn: async (id: string) => {
      const { error } = await api.DELETE('/api/v1/users/{user_id}', {
        params: { path: { user_id: id } },
      })
      if (error) throw new ApiRequestError(error)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['users'] })
      void qc.invalidateQueries({ queryKey: ['tickets'] })
      toast.success('Deactivated; their open tickets went back to Unassigned')
    },
    onError: (e) => toast.error(errorMessage(e)),
  })

  return (
    <div>
      <PageHeader
        title="Team"
        actions={isAdmin && <Button onClick={() => setEditing('new')}>Add employee</Button>}
      />
      {users.isPending ? (
        <Spinner />
      ) : users.isError ? (
        <ErrorState message={errorMessage(users.error)} onRetry={() => void users.refetch()} />
      ) : users.data.length === 0 ? (
        <EmptyState title="No employees yet" />
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-muted-foreground text-left text-xs">
              <tr className="border-border border-b">
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Department</th>
                <th className="px-4 py-2 font-medium">Skills</th>
                <th className="px-4 py-2 font-medium">Open</th>
                <th className="px-4 py-2 font-medium">Availability</th>
                {isAdmin && <th className="px-4 py-2" />}
              </tr>
            </thead>
            <tbody>
              {users.data.map((u) => (
                <tr key={u.id} className="border-border border-b last:border-0">
                  <td className="px-4 py-3">
                    <div className="font-medium">{u.full_name}</div>
                    <div className="text-muted-foreground text-xs">
                      {u.email} · {titleCase(u.role)}
                    </div>
                  </td>
                  <td className="px-4 py-3">{u.department?.name ?? '—'}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {u.skills.map((s) => (
                        <Badge key={s.id} className="bg-muted text-foreground">
                          {s.name}
                        </Badge>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 tabular-nums">{u.open_tickets}</td>
                  <td className="px-4 py-3">{titleCase(u.availability)}</td>
                  {isAdmin && (
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <Button size="sm" variant="ghost" onClick={() => setEditing(u)}>
                        Edit
                      </Button>
                      {u.id !== me.id && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-danger"
                          onClick={() => {
                            if (
                              window.confirm(
                                `Deactivate ${u.full_name}? Their open tickets return to Unassigned.`,
                              )
                            )
                              deactivate.mutate(u.id)
                          }}
                        >
                          Deactivate
                        </Button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {editing && (
        <EmployeeDialog
          user={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  )
}

function EmployeeDialog({ user, onClose }: { user: UserOut | null; onClose: () => void }) {
  const reference = useReference()
  const qc = useQueryClient()
  const [d, setD] = useState<Draft>(
    user
      ? {
          ...emptyDraft,
          full_name: user.full_name,
          email: user.email,
          role: user.role,
          department_id: user.department?.id ?? '',
          availability: user.availability,
          skills: user.skills.map((s) => s.name).join(', '),
        }
      : emptyDraft,
  )
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setD((p) => ({ ...p, [k]: v }))
  const skills = d.skills
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)

  const save = useMutation({
    mutationFn: async () => {
      const department_id = d.department_id || null
      if (user) {
        const { error } = await api.PATCH('/api/v1/users/{user_id}', {
          params: { path: { user_id: user.id } },
          body: {
            full_name: d.full_name,
            role: d.role,
            department_id,
            availability: d.availability,
            skills,
          },
        })
        if (error) throw new ApiRequestError(error)
      } else {
        const { error } = await api.POST('/api/v1/users', {
          body: { ...d, department_id, skills },
        })
        if (error) throw new ApiRequestError(error)
      }
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['users'] })
      toast.success(user ? 'Employee updated' : 'Employee added')
      onClose()
    },
    onError: (e) => toast.error(errorMessage(e)),
  })

  return (
    <Dialog title={user ? `Edit ${user.full_name}` : 'Add employee'} onClose={onClose}>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault()
          save.mutate()
        }}
      >
        <Field label="Full name" htmlFor="emp-name">
          <Input
            id="emp-name"
            autoFocus
            required
            value={d.full_name}
            onChange={(e) => set('full_name', e.target.value)}
          />
        </Field>
        {!user && (
          <>
            <Field label="Email" htmlFor="emp-email">
              <Input
                id="emp-email"
                type="email"
                required
                value={d.email}
                onChange={(e) => set('email', e.target.value)}
              />
            </Field>
            <Field label="Temporary password" htmlFor="emp-pw" hint="At least 10 characters">
              <Input
                id="emp-pw"
                type="password"
                required
                minLength={10}
                value={d.password}
                onChange={(e) => set('password', e.target.value)}
              />
            </Field>
          </>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Role" htmlFor="emp-role">
            <Select
              id="emp-role"
              value={d.role}
              onChange={(e) => set('role', e.target.value as Role)}
            >
              <option value="AGENT">Agent</option>
              <option value="ADMIN">Admin</option>
            </Select>
          </Field>
          <Field label="Availability" htmlFor="emp-avail">
            <Select
              id="emp-avail"
              value={d.availability}
              onChange={(e) => set('availability', e.target.value as Availability)}
            >
              <option value="AVAILABLE">Available</option>
              <option value="BUSY">Busy</option>
              <option value="ON_LEAVE">On leave</option>
            </Select>
          </Field>
        </div>
        <Field label="Department" htmlFor="emp-dept">
          <Select
            id="emp-dept"
            value={d.department_id}
            onChange={(e) => set('department_id', e.target.value)}
          >
            <option value="">None</option>
            {reference.data?.departments.map((dep) => (
              <option key={dep.id} value={dep.id}>
                {dep.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field
          label="Skills"
          htmlFor="emp-skills"
          hint={`Comma-separated. Known: ${reference.data?.skills.map((s) => s.name).join(', ') ?? '…'}`}
        >
          <Input id="emp-skills" value={d.skills} onChange={(e) => set('skills', e.target.value)} />
        </Field>
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={save.isPending}>
            Save
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
