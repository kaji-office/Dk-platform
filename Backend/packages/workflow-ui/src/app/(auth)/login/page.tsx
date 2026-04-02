'use client'

import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useLogin } from '@/api/auth'
import { useAuthStore } from '@/stores/authStore'

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
})
type FormValues = z.infer<typeof schema>

export default function LoginPage() {
  const router = useRouter()
  const loginMutation = useLogin()
  const setAuth = useAuthStore((s) => s.setAuth)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  async function onSubmit(values: FormValues) {
    const result = await loginMutation.mutateAsync(values)
    // Store access token + refresh token in memory
    setAuth(result.access_token, result.refresh_token, {
      id: result.user_id,
      email: values.email,
      name: '',
      tenant_id: result.tenant_id,
      role: 'owner',
      is_verified: true,
      created_at: '',
    })
    router.push('/workflows')
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Sign in</h1>
        <p className="text-sm text-muted-foreground mt-1">Enter your credentials to continue</p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="text-sm font-medium">Email</label>
          <input
            {...register('email')}
            type="email"
            autoComplete="email"
            className="mt-1 w-full rounded-md border border-input px-3 py-2 text-sm"
            placeholder="you@example.com"
          />
          {errors.email && (
            <p className="text-xs text-destructive mt-1">{errors.email.message}</p>
          )}
        </div>

        <div>
          <label className="text-sm font-medium">Password</label>
          <input
            {...register('password')}
            type="password"
            autoComplete="current-password"
            className="mt-1 w-full rounded-md border border-input px-3 py-2 text-sm"
          />
          {errors.password && (
            <p className="text-xs text-destructive mt-1">{errors.password.message}</p>
          )}
        </div>

        {loginMutation.isError && (
          <p className="text-sm text-destructive">
            Invalid email or password.
          </p>
        )}

        <button
          type="submit"
          disabled={isSubmitting || loginMutation.isPending}
          className="w-full rounded-md bg-primary text-primary-foreground py-2 text-sm font-medium hover:opacity-90 disabled:opacity-50"
        >
          {loginMutation.isPending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>

      <div className="text-sm text-center space-y-1">
        <Link href="/forgot-password" className="text-muted-foreground hover:underline block">
          Forgot password?
        </Link>
        <span className="text-muted-foreground">Don&apos;t have an account? </span>
        <Link href="/signup" className="hover:underline">Sign up</Link>
      </div>
    </div>
  )
}
