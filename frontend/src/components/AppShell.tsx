import { useMutation, useQueryClient } from '@tanstack/react-query'
import { LogOut, Moon, Sun, Ticket } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { toast } from 'sonner'
import { Button, Select, cn } from '@/components/ui'
import { api, errorMessage, unwrap } from '@/lib/api/client'
import { useTheme } from '@/lib/theme'
import { useAuth, useMe } from '@/features/auth/authStore'
import { useLogout } from '@/features/auth/hooks'
import type { Availability, Me, Role } from '@/lib/api/types'

const LINKS: { to: string; label: string; roles: Role[] }[] = [
  { to: '/dashboard', label: 'Dashboard', roles: ['ADMIN', 'AGENT'] },
  { to: '/queue', label: 'Queue', roles: ['ADMIN', 'AGENT'] },
  { to: '/my-tickets', label: 'My tickets', roles: ['REQUESTER', 'AGENT', 'ADMIN'] },
  { to: '/team', label: 'Team', roles: ['ADMIN', 'AGENT'] },
]

function useAvailability(user: Me) {
  const setUser = useAuth((s) => s.setUser)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (availability: Availability) =>
      unwrap(
        await api.PATCH('/api/v1/users/{user_id}', {
          params: { path: { user_id: user.id } },
          body: { availability },
        }),
      ),
    onSuccess: (updated) => {
      setUser({ ...user, availability: updated.availability })
      void qc.invalidateQueries({ queryKey: ['users'] })
      toast.success('Availability updated')
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
}

export function AppShell() {
  const user = useMe()
  const logout = useLogout()
  const { theme, toggle } = useTheme()
  const availability = useAvailability(user)

  return (
    <div className="min-h-dvh">
      <header className="border-border bg-card/80 sticky top-0 z-10 border-b backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
          <NavLink
            to="/"
            className="flex shrink-0 items-center gap-2 font-semibold whitespace-nowrap"
          >
            <Ticket className="text-primary size-5" aria-hidden />
            AI Ticketing
          </NavLink>
          <nav className="flex flex-1 items-center gap-1 overflow-x-auto">
            {LINKS.filter((l) => l.roles.includes(user.role)).map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                className={({ isActive }) =>
                  cn(
                    'rounded-md px-3 py-1.5 text-sm font-medium whitespace-nowrap',
                    isActive ? 'bg-muted text-foreground' : 'text-muted-foreground hover:bg-muted',
                  )
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>

          {user.role === 'AGENT' && (
            // Inputs are w-full; the wrapper sets the width so the nav links keep their room.
            <div className="w-32 shrink-0">
              <Select
                aria-label="Your availability"
                className="h-9"
                value={user.availability}
                disabled={availability.isPending}
                onChange={(e) => availability.mutate(e.target.value as Availability)}
              >
                <option value="AVAILABLE">Available</option>
                <option value="BUSY">Busy</option>
                <option value="ON_LEAVE">On leave</option>
              </Select>
            </div>
          )}

          <Button variant="ghost" size="sm" onClick={toggle} aria-label="Toggle theme">
            {theme === 'dark' ? <Moon className="size-4" /> : <Sun className="size-4" />}
          </Button>
          <NavLink
            to="/settings/profile"
            className="text-muted-foreground hover:text-foreground hidden text-sm sm:block"
          >
            {user.full_name}
          </NavLink>
          <Button variant="ghost" size="sm" onClick={() => logout.mutate()} aria-label="Sign out">
            <LogOut className="size-4" />
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}

export function PageHeader({ title, actions }: { title: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      {actions}
    </div>
  )
}
