import { PageHeader } from '@/components/AppShell'
import { EmptyState, ErrorState } from '@/components/states'
import { Button, ButtonLink } from '@/components/ui'
import { errorMessage } from '@/lib/api/client'
import { useMe } from '@/features/auth/authStore'
import { useTickets } from './hooks'
import { TicketList, TicketListSkeleton } from './TicketList'

export default function MyTicketsPage() {
  const user = useMe()
  const query = useTickets({ requester_id: user.id, sort: '-created_at' })
  const items = query.data?.pages.flatMap((p) => p.items) ?? []

  return (
    <div>
      <PageHeader
        title="My tickets"
        actions={<ButtonLink to="/tickets/new">New ticket</ButtonLink>}
      />
      {query.isPending ? (
        <TicketListSkeleton />
      ) : query.isError ? (
        <ErrorState message={errorMessage(query.error)} onRetry={() => void query.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState title="No tickets yet" hint="Submit one and we'll triage it in seconds." />
      ) : (
        <>
          <TicketList items={items} />
          {query.hasNextPage && (
            <div className="mt-4 text-center">
              <Button
                variant="outline"
                loading={query.isFetchingNextPage}
                onClick={() => void query.fetchNextPage()}
              >
                Load more
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
