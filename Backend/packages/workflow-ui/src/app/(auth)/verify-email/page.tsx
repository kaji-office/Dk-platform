'use client'

import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useVerifyEmail } from '@/api/auth'

function VerifyEmailContent() {
  const params = useSearchParams()
  const token = params.get('token') ?? ''
  const mutation = useVerifyEmail()
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (!token) return
    mutation.mutateAsync(token).then(() => setDone(true)).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  if (!token) {
    return <p className="text-sm text-muted-foreground">No token provided.</p>
  }
  if (mutation.isPending) {
    return <p className="text-sm text-muted-foreground">Verifying…</p>
  }
  if (mutation.isError) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-destructive">Verification link is invalid or expired.</p>
        <Link href="/login" className="text-sm hover:underline">Back to sign in</Link>
      </div>
    )
  }
  return (
    <div className="space-y-3">
      <p className="text-sm font-medium">Email verified ✓</p>
      <Link href="/login" className="text-sm hover:underline">Sign in to continue</Link>
    </div>
  )
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted-foreground">Loading…</p>}>
      <VerifyEmailContent />
    </Suspense>
  )
}
