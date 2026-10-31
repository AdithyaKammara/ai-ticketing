import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { Button, Card, Field, Input } from '@/components/ui'
import { roleHome } from '@/app/RequireAuth'
import { useAuth } from './authStore'
import { useRegister } from './hooks'

const schema = z.object({
  full_name: z.string().trim().min(1, 'Enter your name').max(120),
  email: z.email('Enter a valid email'),
  password: z.string().min(10, 'Use at least 10 characters').max(128),
})
type Form = z.infer<typeof schema>

export default function RegisterPage() {
  const reg = useRegister()
  const user = useAuth((s) => s.user)
  const navigate = useNavigate()
  const form = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { full_name: '', email: '', password: '' },
  })

  useEffect(() => {
    if (user) void navigate(roleHome(user), { replace: true })
  }, [user, navigate])

  return (
    <div className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-6 px-4 py-10">
      <Card className="space-y-4 p-6">
        <h1 className="text-lg font-semibold">Create your account</h1>
        <form
          className="space-y-4"
          onSubmit={(e) => void form.handleSubmit((v) => reg.mutate(v))(e)}
          noValidate
        >
          <Field
            label="Full name"
            htmlFor="full_name"
            error={form.formState.errors.full_name?.message}
          >
            <Input id="full_name" autoComplete="name" {...form.register('full_name')} />
          </Field>
          <Field label="Email" htmlFor="email" error={form.formState.errors.email?.message}>
            <Input id="email" type="email" autoComplete="email" {...form.register('email')} />
          </Field>
          <Field
            label="Password"
            htmlFor="password"
            error={form.formState.errors.password?.message}
            hint="At least 10 characters"
          >
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              {...form.register('password')}
            />
          </Field>
          <Button type="submit" className="w-full" loading={reg.isPending || reg.isSuccess}>
            Create account
          </Button>
        </form>
        <p className="text-muted-foreground text-center text-sm">
          Already have an account?{' '}
          <Link to="/login" className="text-primary underline">
            Sign in
          </Link>
        </p>
      </Card>
    </div>
  )
}
