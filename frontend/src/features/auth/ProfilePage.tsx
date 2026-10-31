import { PageHeader } from '@/components/AppShell'
import { Card } from '@/components/ui'
import { titleCase } from '@/lib/constants'
import { useAuth } from './authStore'

export default function ProfilePage() {
  const user = useAuth((s) => s.user)
  if (!user) return null

  const rows = [
    ['Name', user.full_name],
    ['Email', user.email],
    ['Role', titleCase(user.role)],
    ['Department', user.department?.name ?? '—'],
    ['Availability', titleCase(user.availability)],
  ]

  return (
    <div className="mx-auto max-w-lg">
      <PageHeader title="Profile" />
      <Card className="divide-border divide-y">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between px-4 py-3 text-sm">
            <span className="text-muted-foreground">{label}</span>
            <span className="font-medium">{value}</span>
          </div>
        ))}
      </Card>
      {user.role === 'AGENT' && (
        <p className="text-muted-foreground mt-3 text-sm">
          Change your availability from the selector in the top bar.
        </p>
      )}
    </div>
  )
}
