'use client'

import { useState } from 'react'
import { useCurrentUser, useUpdateProfile, useApiKeys, useCreateApiKey, useDeleteApiKey } from '@/api/users'
import { useUIStore } from '@/stores/uiStore'

export default function ProfilePage() {
  const { data: user, isLoading } = useCurrentUser()
  const updateProfile = useUpdateProfile()
  const { data: apiKeys } = useApiKeys()
  const createApiKey = useCreateApiKey()
  const deleteApiKey = useDeleteApiKey()
  const addToast = useUIStore((s) => s.addToast)

  const [name, setName] = useState('')
  const [newKeyName, setNewKeyName] = useState('')
  const [revealedKey, setRevealedKey] = useState<string | null>(null)

  // Pre-fill name once user loads
  const displayName = name !== '' ? name : (user?.name ?? '')

  function handleSaveProfile(e: React.FormEvent) {
    e.preventDefault()
    updateProfile.mutate(
      { name: displayName },
      {
        onSuccess: () => addToast({ title: 'Profile updated', variant: 'default' }),
        onError: () => addToast({ title: 'Update failed', variant: 'destructive' }),
      },
    )
  }

  function handleCreateKey(e: React.FormEvent) {
    e.preventDefault()
    if (!newKeyName.trim()) return
    createApiKey.mutate(newKeyName.trim(), {
      onSuccess: (data) => {
        setNewKeyName('')
        setRevealedKey((data as { key?: string }).key ?? null)
      },
      onError: () => addToast({ title: 'Failed to create key', variant: 'destructive' }),
    })
  }

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>
  }

  return (
    <div className="space-y-8 max-w-xl">
      <h1 className="text-lg font-semibold">Profile & Settings</h1>

      {/* Profile form */}
      <section className="space-y-3">
        <h2 className="text-sm font-medium">Account</h2>
        <form onSubmit={handleSaveProfile} className="space-y-3">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Name</label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-md border border-input px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Email</label>
            <input
              type="email"
              value={user?.email ?? ''}
              disabled
              className="w-full rounded-md border border-input px-3 py-1.5 text-sm bg-muted text-muted-foreground"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Role:</span>
            <span className="text-xs font-medium capitalize">{user?.role}</span>
            {user?.is_verified && (
              <span className="ml-2 text-xs text-green-600">Verified</span>
            )}
          </div>
          <button
            type="submit"
            disabled={updateProfile.isPending}
            className="px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm disabled:opacity-50"
          >
            {updateProfile.isPending ? 'Saving…' : 'Save changes'}
          </button>
        </form>
      </section>

      {/* API keys */}
      <section className="space-y-3">
        <h2 className="text-sm font-medium">API Keys</h2>

        {/* Revealed key — show once */}
        {revealedKey && (
          <div className="rounded-md border border-yellow-300 bg-yellow-50 p-3 space-y-1">
            <p className="text-xs font-medium text-yellow-800">
              Copy this key now — it won&apos;t be shown again.
            </p>
            <code className="block text-xs font-mono break-all text-yellow-900">{revealedKey}</code>
            <button
              onClick={() => {
                navigator.clipboard.writeText(revealedKey)
                addToast({ title: 'Copied to clipboard', variant: 'default' })
              }}
              className="text-xs underline text-yellow-700"
            >
              Copy
            </button>
          </div>
        )}

        {/* Existing keys */}
        <div className="rounded-md border border-border divide-y divide-border">
          {(apiKeys ?? []).length === 0 && (
            <p className="px-3 py-2 text-sm text-muted-foreground">No API keys yet.</p>
          )}
          {(apiKeys ?? []).map((key) => (
            <div key={key.id} className="flex items-center justify-between px-3 py-2">
              <div>
                <p className="text-sm font-medium">{key.name}</p>
                <p className="text-xs text-muted-foreground font-mono">{key.key_prefix}…</p>
                {key.last_used_at && (
                  <p className="text-xs text-muted-foreground">
                    Last used {new Date(key.last_used_at).toLocaleDateString()}
                  </p>
                )}
              </div>
              <button
                onClick={() =>
                  deleteApiKey.mutate(key.id, {
                    onError: () => addToast({ title: 'Delete failed', variant: 'destructive' }),
                  })
                }
                className="text-xs text-destructive hover:underline"
              >
                Revoke
              </button>
            </div>
          ))}
        </div>

        {/* Create new key */}
        <form onSubmit={handleCreateKey} className="flex gap-2">
          <input
            type="text"
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            placeholder="Key name (e.g. CI/CD)"
            className="flex-1 rounded-md border border-input px-3 py-1.5 text-sm"
          />
          <button
            type="submit"
            disabled={createApiKey.isPending || !newKeyName.trim()}
            className="px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm disabled:opacity-50"
          >
            {createApiKey.isPending ? 'Creating…' : 'Create key'}
          </button>
        </form>
      </section>
    </div>
  )
}
