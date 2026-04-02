'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import Link from 'next/link'
import { usePasswordResetRequest } from '@/api/auth'

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false)
  const mutation = usePasswordResetRequest()
  const { register, handleSubmit } = useForm<{ email: string }>()

  async function onSubmit({ email }: { email: string }) {
    await mutation.mutateAsync(email)
    // Always show "email sent" — server returns 204 regardless to prevent enumeration
    setSent(true)
  }

  if (sent) {
    return (
      <div className="space-y-4 text-center">
        <h1 className="text-xl font-semibold">Check your email</h1>
        <p className="text-sm text-muted-foreground">
          If an account exists for that email, a reset link has been sent.
        </p>
        <Link href="/login" className="text-sm hover:underline">Back to sign in</Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Reset password</h1>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="text-sm font-medium">Email address</label>
          <input
            {...register('email', { required: true })}
            type="email"
            className="mt-1 w-full rounded-md border border-input px-3 py-2 text-sm"
            placeholder="you@example.com"
          />
        </div>
        <button
          type="submit"
          disabled={mutation.isPending}
          className="w-full rounded-md bg-primary text-primary-foreground py-2 text-sm font-medium disabled:opacity-50"
        >
          {mutation.isPending ? 'Sending…' : 'Send reset email'}
        </button>
      </form>
      <Link href="/login" className="text-sm text-muted-foreground hover:underline block text-center">
        Back to sign in
      </Link>
    </div>
  )
}
