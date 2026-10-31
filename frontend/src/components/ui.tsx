import { Loader2 } from 'lucide-react'
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react'
import { Link, type LinkProps } from 'react-router-dom'

// A handful of accessible primitives, hand-written on the theme tokens. Fewer files than a
// full shadcn install for the small set these screens actually use.
export const cn = (...xs: (string | false | null | undefined)[]): string =>
  xs.filter(Boolean).join(' ')

const focus = 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary'
const control =
  'w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground disabled:opacity-50'

type Variant = 'primary' | 'outline' | 'ghost' | 'danger'
type Size = 'sm' | 'md'

export function buttonClass(
  variant: Variant = 'primary',
  size: Size = 'md',
  extra?: string,
): string {
  const variants: Record<Variant, string> = {
    primary: 'bg-primary text-primary-foreground hover:opacity-90',
    outline: 'border border-border bg-card text-foreground hover:bg-muted',
    ghost: 'text-foreground hover:bg-muted',
    danger: 'bg-danger text-white hover:opacity-90',
  }
  const sizes: Record<Size, string> = { sm: 'h-8 px-3 text-sm', md: 'h-10 px-4 text-sm' }
  return cn(
    'inline-flex items-center justify-center gap-2 rounded-md font-medium transition disabled:cursor-not-allowed disabled:opacity-50',
    focus,
    variants[variant],
    sizes[size],
    extra,
  )
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  size?: Size
  loading?: boolean
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading,
  disabled,
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={buttonClass(variant, size, className)}
      disabled={disabled ?? loading}
      {...rest}
    >
      {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  )
}

export function ButtonLink({
  variant = 'primary',
  size = 'md',
  className,
  children,
  ...rest
}: LinkProps & { variant?: Variant; size?: Size }) {
  return (
    <Link className={buttonClass(variant, size, className)} {...rest}>
      {children}
    </Link>
  )
}

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(control, focus, className)} {...rest} />
}

export function Textarea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(control, focus, 'min-h-28 resize-y', className)} {...rest} />
}

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(control, focus, 'pr-8', className)} {...rest}>
      {children}
    </select>
  )
}

export function Field({
  label,
  htmlFor,
  error,
  hint,
  children,
}: {
  label: string
  htmlFor?: string
  error?: string
  hint?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium">
        {label}
      </label>
      {children}
      {error ? (
        <p className="text-danger text-sm" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="text-muted-foreground text-xs">{hint}</p>
      ) : null}
    </div>
  )
}

export function Badge({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        className,
      )}
    >
      {children}
    </span>
  )
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn('border-border bg-card rounded-lg border', className)}>{children}</div>
}

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div
      className="text-muted-foreground flex items-center justify-center gap-2 py-12"
      role="status"
    >
      <Loader2 className="size-5 animate-spin" aria-hidden />
      <span>{label}…</span>
    </div>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('bg-muted animate-pulse rounded-md', className)} aria-hidden />
}

export function Dialog({
  title,
  onClose,
  children,
}: {
  title: string
  onClose: () => void
  children: ReactNode
}) {
  // ponytail: Esc + overlay close + aria-modal, no focus trap. Add a trap if these grow
  // into multi-field flows users tab through heavily.
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 pt-16"
      onClick={onClose}
      onKeyDown={(e) => e.key === 'Escape' && onClose()}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="border-border bg-card w-full max-w-md rounded-lg border p-5 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-4 text-lg font-semibold">{title}</h2>
        {children}
      </div>
    </div>
  )
}
