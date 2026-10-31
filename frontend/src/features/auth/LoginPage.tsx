import { zodResolver } from '@hookform/resolvers/zod'
import { Ticket } from 'lucide-react'
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { Button, Card, Field, Input } from '@/components/ui'
import { roleHome } from '@/app/RequireAuth'
import { useAuth } from './authStore'
import { useLogin } from './hooks'

const schema = z.object({
  email: z.email('Enter a valid email'),
  password: z.string().min(1, 'Enter your password'),
})
type Form = z.infer<typeof schema>

const DEMO = [
  { role: 'Requester', email: 'requester@acme.example' },
  { role: 'Agent', email: 'agent@acme.example' },
  { role: 'Admin', email: 'admin@acme.example' },
]
const DEMO_PASSWORD = 'ticketing-demo'

export default function LoginPage() {
  const login = useLogin()
  const user = useAuth((s) => s.user)
  const navigate = useNavigate()
  const location = useLocation() as { state?: { from?: { pathname: string } } }

  const form = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '' },
  })

  useEffect(() => {
    if (user) void navigate(location.state?.from?.pathname ?? roleHome(user), { replace: true })
  }, [user, navigate, location.state])

  return (
    <div className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-6 px-4 py-10">
      <div className="flex items-center gap-2 text-xl font-semibold">
        <Ticket className="text-primary size-6" aria-hidden />
        AI Ticketing
      </div>

      <Card className="space-y-4 p-6">
        <h1 className="text-lg font-semibold">Sign in</h1>
        <form
          className="space-y-4"
          onSubmit={(e) => void form.handleSubmit((v) => login.mutate(v))(e)}
          noValidate
        >
          <Field label="Email" htmlFor="email" error={form.formState.errors.email?.message}>
            <Input id="email" type="email" autoComplete="email" {...form.register('email')} />
          </Field>
          <Field
            label="Password"
            htmlFor="password"
            error={form.formState.errors.password?.message}
          >
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              {...form.register('password')}
            />
          </Field>
          <Button type="submit" className="w-full" loading={login.isPending}>
            Sign in
          </Button>
        </form>
        <p className="text-muted-foreground text-center text-sm">
          No account?{' '}
          <Link to="/register" className="text-primary underline">
            Register
          </Link>
        </p>
      </Card>

      <div className="space-y-2">
        <p className="text-muted-foreground text-center text-xs">Try a demo account</p>
        <div className="grid grid-cols-3 gap-2">
          {DEMO.map((d) => (
            <Button
              key={d.role}
              variant="outline"
              size="sm"
              disabled={login.isPending}
              onClick={() => login.mutate({ email: d.email, password: DEMO_PASSWORD })}
            >
              {d.role}
            </Button>
          ))}
        </div>
      </div>
    </div>
  )
}
