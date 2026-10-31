import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom'
import { AppShell } from '@/components/AppShell'
import { Spinner } from '@/components/ui'
import { RequireAuth, roleHome } from '@/app/RequireAuth'
import { useAuth } from '@/features/auth/authStore'

const LoginPage = lazy(() => import('@/features/auth/LoginPage'))
const RegisterPage = lazy(() => import('@/features/auth/RegisterPage'))
const ProfilePage = lazy(() => import('@/features/auth/ProfilePage'))
const NewTicketPage = lazy(() => import('@/features/tickets/NewTicketPage'))
const MyTicketsPage = lazy(() => import('@/features/tickets/MyTicketsPage'))
const QueuePage = lazy(() => import('@/features/tickets/QueuePage'))
const TicketDetailPage = lazy(() => import('@/features/tickets/TicketDetailPage'))
const TeamPage = lazy(() => import('@/features/team/TeamPage'))
const DashboardPage = lazy(() => import('@/features/analytics/DashboardPage'))

function Lazy({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<Spinner />}>{children}</Suspense>
}

function HomeRedirect() {
  const user = useAuth((s) => s.user)
  const ready = useAuth((s) => s.ready)
  if (!ready) return <Spinner />
  return <Navigate to={user ? roleHome(user) : '/login'} replace />
}

const protectedRoute = (
  element: React.ReactNode,
  roles?: Parameters<typeof RequireAuth>[0]['roles'],
) => ({
  element: (
    <RequireAuth roles={roles}>
      <AppShell />
    </RequireAuth>
  ),
  children: [{ index: true, element: <Lazy>{element}</Lazy> }],
})

export const routes: RouteObject[] = [
  {
    path: '/login',
    element: (
      <Lazy>
        <LoginPage />
      </Lazy>
    ),
  },
  {
    path: '/register',
    element: (
      <Lazy>
        <RegisterPage />
      </Lazy>
    ),
  },
  { path: '/', element: <HomeRedirect /> },
  { path: '/my-tickets', ...protectedRoute(<MyTicketsPage />) },
  { path: '/tickets/new', ...protectedRoute(<NewTicketPage />) },
  { path: '/tickets/:id', ...protectedRoute(<TicketDetailPage />) },
  { path: '/queue', ...protectedRoute(<QueuePage />, ['AGENT', 'ADMIN']) },
  { path: '/team', ...protectedRoute(<TeamPage />, ['AGENT', 'ADMIN']) },
  { path: '/dashboard', ...protectedRoute(<DashboardPage />, ['AGENT', 'ADMIN']) },
  { path: '/settings/profile', ...protectedRoute(<ProfilePage />) },
  {
    path: '*',
    element: (
      <div className="mx-auto max-w-md p-12 text-center">
        <p className="mb-3 text-lg font-medium">Page not found</p>
        <a className="text-primary underline" href="/">
          Back home
        </a>
      </div>
    ),
  },
]

export const router = createBrowserRouter(routes)
