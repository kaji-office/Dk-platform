'use client'

import { useState } from 'react'
import {
  useInboundWebhooks,
  useCreateInboundWebhook,
  useUpdateInboundWebhook,
  useDeleteInboundWebhook,
} from '@/api/webhooks'
import { useWorkflows } from '@/api/workflows'
import { useUIStore } from '@/stores/uiStore'
import type { InboundWebhook } from '@/types/api'
import { Copy, Trash2, Plus, X } from 'lucide-react'

// ── Create dialog ─────────────────────────────────────────────────────────────

function CreateWebhookDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void
  onCreated: (secret: string) => void
}) {
  const { data: workflows } = useWorkflows()
  const createMutation = useCreateInboundWebhook()
  const [name, setName] = useState('')
  const [workflowId, setWorkflowId] = useState('')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim() || !workflowId) return
    createMutation.mutate(
      { name: name.trim(), workflow_id: workflowId },
      {
        onSuccess: (data) => {
          onCreated(data.secret ?? '')
          onClose()
        },
      },
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-background rounded-lg border border-border shadow-lg w-full max-w-md p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">New Webhook</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={16} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Stripe payments"
              className="w-full rounded-md border border-input px-3 py-1.5 text-sm"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Trigger Workflow</label>
            <select
              value={workflowId}
              onChange={(e) => setWorkflowId(e.target.value)}
              className="w-full rounded-md border border-input px-3 py-1.5 text-sm"
              required
            >
              <option value="">Select a workflow…</option>
              {(workflows ?? []).map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 rounded-md border border-border text-sm"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm disabled:opacity-50"
            >
              {createMutation.isPending ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Secret reveal modal (shown once after creation) ───────────────────────────

function SecretModal({ secret, onClose }: { secret: string; onClose: () => void }) {
  const addToast = useUIStore((s) => s.addToast)
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-background rounded-lg border border-yellow-300 shadow-lg w-full max-w-md p-5 space-y-4">
        <h2 className="text-sm font-semibold text-yellow-800">Save your webhook secret</h2>
        <p className="text-xs text-yellow-700">
          This secret is shown only once. Store it securely — you won&apos;t be able to retrieve it again.
        </p>
        <div className="flex items-center gap-2 rounded-md border border-border bg-muted p-2">
          <code className="text-xs font-mono flex-1 break-all">{secret}</code>
          <button
            onClick={() => {
              navigator.clipboard.writeText(secret)
              addToast({ title: 'Copied to clipboard', variant: 'default' })
            }}
            className="shrink-0 text-muted-foreground hover:text-foreground"
          >
            <Copy size={14} />
          </button>
        </div>
        <div className="flex justify-end">
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm"
          >
            I&apos;ve saved it
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Webhook row ───────────────────────────────────────────────────────────────

function WebhookRow({ webhook }: { webhook: InboundWebhook }) {
  const updateMutation = useUpdateInboundWebhook()
  const deleteMutation = useDeleteInboundWebhook()
  const addToast = useUIStore((s) => s.addToast)

  function toggleActive() {
    updateMutation.mutate({ id: webhook.id, active: !webhook.active })
  }

  function handleDelete() {
    deleteMutation.mutate(webhook.id, {
      onError: () => addToast({ title: 'Delete failed', variant: 'destructive' }),
    })
  }

  return (
    <div className="flex items-start gap-4 px-4 py-3 border-b border-border last:border-b-0">
      <div className="flex-1 min-w-0 space-y-0.5">
        <p className="text-sm font-medium truncate">{webhook.name}</p>
        {webhook.endpoint_url ? (
          <p className="text-xs font-mono text-muted-foreground truncate">{webhook.endpoint_url}</p>
        ) : (
          <p className="text-xs text-muted-foreground italic">No endpoint URL</p>
        )}
        <p className="text-xs text-muted-foreground">
          Workflow: <span className="font-mono">{webhook.workflow_id}</span>
        </p>
      </div>

      <div className="flex items-center gap-3 shrink-0">
        {/* Active toggle */}
        <button
          onClick={toggleActive}
          disabled={updateMutation.isPending}
          className={`text-xs px-2 py-0.5 rounded-full font-medium transition-colors ${
            webhook.active
              ? 'bg-green-100 text-green-700'
              : 'bg-gray-100 text-gray-500'
          }`}
        >
          {webhook.active ? 'Active' : 'Inactive'}
        </button>

        {/* Copy endpoint URL */}
        {webhook.endpoint_url && (
          <button
            onClick={() => {
              navigator.clipboard.writeText(webhook.endpoint_url!)
              addToast({ title: 'URL copied', variant: 'default' })
            }}
            className="text-muted-foreground hover:text-foreground"
            title="Copy endpoint URL"
          >
            <Copy size={14} />
          </button>
        )}

        {/* Delete */}
        <button
          onClick={handleDelete}
          disabled={deleteMutation.isPending}
          className="text-muted-foreground hover:text-destructive disabled:opacity-40"
          title="Delete webhook"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function IntegrationsPage() {
  const { data: webhooks, isLoading } = useInboundWebhooks()
  const [showCreate, setShowCreate] = useState(false)
  const [revealSecret, setRevealSecret] = useState<string | null>(null)

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Webhooks</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm"
        >
          <Plus size={14} /> New Webhook
        </button>
      </div>

      <p className="text-sm text-muted-foreground">
        Inbound webhooks let external services trigger your workflows via HTTP POST.
      </p>

      <div className="rounded-md border border-border">
        {isLoading && (
          <p className="px-4 py-3 text-sm text-muted-foreground">Loading…</p>
        )}
        {!isLoading && (webhooks ?? []).length === 0 && (
          <p className="px-4 py-3 text-sm text-muted-foreground">
            No webhooks yet. Create one to get started.
          </p>
        )}
        {(webhooks ?? []).map((wh) => (
          <WebhookRow key={wh.id} webhook={wh} />
        ))}
      </div>

      {showCreate && (
        <CreateWebhookDialog
          onClose={() => setShowCreate(false)}
          onCreated={(secret) => {
            setRevealSecret(secret)
          }}
        />
      )}

      {revealSecret && (
        <SecretModal secret={revealSecret} onClose={() => setRevealSecret(null)} />
      )}
    </div>
  )
}
