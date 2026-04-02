'use client'

import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useRegister } from '@/api/auth'

const schema = z.object({
  name: z.string().min(2),
  email: z.string().email(),
  password: z.string().min(8),
  tenant_name: z.string().min(2, 'Organisation name required'),
})
type FormValues = z.infer<typeof schema>

export default function SignupPage() {
  const router = useRouter()
  const registerMutation = useRegister()

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  async function onSubmit(values: FormValues) {
    await registerMutation.mutateAsync(values)
    // Registration succeeds → server sends verification email
    // Show "check your email" screen (do NOT auto-navigate to dashboard until verified)
    router.push('/login?registered=1')
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Create account</h1>
        <p className="text-sm text-muted-foreground mt-1">
          A verification email will be sent after registration.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {[
          { name: 'name' as const,        label: 'Your name',           type: 'text',     placeholder: 'Jane Smith' },
          { name: 'tenant_name' as const, label: 'Organisation',        type: 'text',     placeholder: 'Acme Corp' },
          { name: 'email' as const,       label: 'Email',               type: 'email',    placeholder: 'jane@acme.com' },
          { name: 'password' as const,    label: 'Password (min 8)',    type: 'password', placeholder: '' },
        ].map(({ name, label, type, placeholder }) => (
          <div key={name}>
            <label className="text-sm font-medium">{label}</label>
            <input
              {...register(name)}
              type={type}
              placeholder={placeholder}
              className="mt-1 w-full rounded-md border border-input px-3 py-2 text-sm"
            />
            {errors[name] && (
              <p className="text-xs text-destructive mt-1">{errors[name]?.message}</p>
            )}
          </div>
        ))}

        {registerMutation.isError && (
          <p className="text-sm text-destructive">
            Registration failed. Email may already be in use.
          </p>
        )}

        <button
          type="submit"
          disabled={isSubmitting || registerMutation.isPending}
          className="w-full rounded-md bg-primary text-primary-foreground py-2 text-sm font-medium hover:opacity-90 disabled:opacity-50"
        >
          {registerMutation.isPending ? 'Creating…' : 'Create account'}
        </button>
      </form>

      <p className="text-sm text-center text-muted-foreground">
        Already have an account?{' '}
        <Link href="/login" className="text-foreground hover:underline">Sign in</Link>
      </p>
    </div>
  )
}
