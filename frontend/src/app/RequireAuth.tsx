import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Spinner } from '@/components/ui'
import { useAuth } from '@/features/auth/authStore'
import type { Me, Role } from '@/lib/api/types'

export function roleHome(user: Me): string {
  if (user.role === 'ADMIN') return '/dashboard'
  if (user.role === 'AGENT') return '/queue'
  return '/my-tickets'
}

export function RequireAuth({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { ready, user } = useAuth()
  const location = useLocation()

  if (!ready) return <Spinner label="Signing you in" />
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  if (roles && !roles.includes(user.role)) return <Navigate to={roleHome(user)} replace />
  return <>{children}</>
}
