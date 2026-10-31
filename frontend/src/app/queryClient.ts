import { QueryClient } from '@tanstack/react-query'
import { apiError } from '@/lib/api/client'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      retry: (count, error) => {
        // Don't retry auth/permission/validation errors; they won't change on retry.
        const code = apiError(error)?.code
        if (
          code &&
          ['UNAUTHENTICATED', 'FORBIDDEN', 'NOT_FOUND', 'VALIDATION_ERROR'].includes(code)
        )
          return false
        return count < 2
      },
    },
  },
})
