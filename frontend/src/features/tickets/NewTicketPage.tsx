import { zodResolver } from '@hookform/resolvers/zod'
import { useForm, useWatch } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { PageHeader } from '@/components/AppShell'
import { Button, Card, Field, Input, Textarea } from '@/components/ui'
import { useCreateTicket } from './hooks'

const schema = z.object({
  title: z.string().trim().min(5, 'At least 5 characters').max(150),
  description: z.string().trim().min(20, 'At least 20 characters').max(5000),
})
type Form = z.infer<typeof schema>

export default function NewTicketPage() {
  const create = useCreateTicket()
  const navigate = useNavigate()
  const form = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { title: '', description: '' },
  })
  const title = useWatch({ control: form.control, name: 'title' })
  const description = useWatch({ control: form.control, name: 'description' })

  const submit = form.handleSubmit((v) => {
    create.mutate(v, { onSuccess: (t) => void navigate(`/tickets/${t.id}`) })
  })

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Submit a ticket" />
      <Card className="p-6">
        <form className="space-y-4" onSubmit={(e) => void submit(e)} noValidate>
          <Field
            label="Title"
            htmlFor="title"
            error={form.formState.errors.title?.message}
            hint={`${title.length}/150`}
          >
            <Input
              id="title"
              placeholder="Short summary of the problem"
              {...form.register('title')}
            />
          </Field>
          <Field
            label="Description"
            htmlFor="description"
            error={form.formState.errors.description?.message}
            hint={`${description.length}/5000 — describe what happened and what you expected`}
          >
            <Textarea id="description" rows={7} {...form.register('description')} />
          </Field>
          <Button type="submit" loading={create.isPending}>
            Submit ticket
          </Button>
        </form>
      </Card>
      <p className="text-muted-foreground mt-3 text-sm">
        We triage every ticket within seconds and either answer it or route it to the right person.
      </p>
    </div>
  )
}
