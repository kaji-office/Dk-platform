'use client'

import { Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { usePasswordReset } from '@/api/auth'

const schema = z.object({
  new_password: z.string().min(8),
  confirm: z.string(),
}).refine((d) => d.new_password === d.confirm, {
  message: 'Passwords do not match',
  path: ['confirm'],
})

function ResetPasswordContent() {
  const params = useSearchParams()
  const token = params.get('token') ?? ''
  const router = useRouter()
  const mutation = usePasswordReset()

  type FormValues = { new_password: string; confirm: string }

  const { register, handleSubmit, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
  })

  async function onSubmit({ new_password }: FormValues) {
    await mutation.mutateAsync({ token, new_password })
    router.push('/login?reset=1')
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Set new password</h1>
      {mutation.isError && (
        <p className="text-sm text-destructive">
          Reset link is invalid or has expired. Please request a new one.
        </p>
      )}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="text-sm font-medium">New password</label>
          <input
            {...register('new_password')}
            type="password"
            className="mt-1 w-full rounded-md border border-input px-3 py-2 text-sm"
          />
          {errors.new_password?.message && (
            <p className="text-xs text-destructive mt-1">{errors.new_password.message as string}</p>
          )}
        </div>
        <div>
          <label className="text-sm font-medium">Confirm password</label>
          <input
            {...register('confirm')}
            type="password"
            className="mt-1 w-full rounded-md border border-input px-3 py-2 text-sm"
          />
          {errors.confirm?.message && (
            <p className="text-xs text-destructive mt-1">{errors.confirm.message as string}</p>
          )}
        </div>
        <button
          type="submit"
          disabled={mutation.isPending}
          className="w-full rounded-md bg-primary text-primary-foreground py-2 text-sm font-medium disabled:opacity-50"
        >
          {mutation.isPending ? 'Updating…' : 'Update password'}
        </button>
      </form>
    </div>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted-foreground">Loading…</p>}>
      <ResetPasswordContent />
    </Suspense>
  )
}
