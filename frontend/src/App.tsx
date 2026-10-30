import { useEffect, useState } from 'react'

type ApiStatus = 'checking' | 'up' | 'down'

const STATUS_TEXT: Record<ApiStatus, string> = {
  checking: 'Checking API…',
  up: 'API is up',
  down: 'API is unreachable',
}

export default function App() {
  const [status, setStatus] = useState<ApiStatus>('checking')

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/v1/health', { signal: controller.signal })
      .then((response) => {
        setStatus(response.ok ? 'up' : 'down')
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          console.error(error)
          setStatus('down')
        }
      })
    return () => {
      controller.abort()
    }
  }, [])

  return (
    <main className="mx-auto flex min-h-dvh max-w-2xl flex-col justify-center gap-4 px-4">
      <h1 className="text-3xl font-semibold tracking-tight">AI Ticketing</h1>
      <p className="text-muted-foreground">
        Internal support tickets, triaged in seconds. The rebuild is in progress.
      </p>
      <p role="status" className="flex items-center gap-2 text-sm">
        <span
          aria-hidden="true"
          className={
            status === 'up'
              ? 'bg-success size-2 rounded-full'
              : status === 'down'
                ? 'bg-danger size-2 rounded-full'
                : 'bg-muted-foreground size-2 rounded-full'
          }
        />
        {STATUS_TEXT[status]}
      </p>
    </main>
  )
}
