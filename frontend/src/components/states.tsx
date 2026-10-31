import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Button, Card } from '@/components/ui'

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <Card className="flex flex-col items-center gap-1 px-6 py-16 text-center">
      <p className="font-medium">{title}</p>
      {hint && <p className="text-muted-foreground text-sm">{hint}</p>}
    </Card>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Card className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      <p className="text-danger font-medium">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </Card>
  )
}

export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled UI error', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="mx-auto max-w-md p-8">
          <ErrorState
            message="This page hit an unexpected error."
            onRetry={() => {
              window.location.reload()
            }}
          />
        </div>
      )
    }
    return this.props.children
  }
}
