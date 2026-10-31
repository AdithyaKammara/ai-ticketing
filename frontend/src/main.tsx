import { QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { Toaster } from 'sonner'
import { ErrorBoundary } from '@/components/states'
import { Spinner } from '@/components/ui'
import { queryClient } from '@/app/queryClient'
import { router } from '@/app/router'
import { useBootstrapAuth } from '@/features/auth/hooks'
import './index.css'

// Restore the session from the refresh cookie before routing, so a signed-in reload lands
// on the right page instead of flashing the login screen.
function Root() {
  const ready = useBootstrapAuth()
  return ready ? <RouterProvider router={router} /> : <Spinner label="Loading" />
}

const root = document.getElementById('root')
if (!root) throw new Error('Root element #root is missing from index.html')

createRoot(root).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <Root />
        <Toaster richColors closeButton position="top-right" />
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
)
