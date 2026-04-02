'use client'

import Link from 'next/link'
import { useWorkflows } from '@/api/workflows'
import { useExecutions } from '@/api/executions'
import { Plus, Play, CheckCircle2, XCircle, Loader2 } from 'lucide-react'

export default function DashboardPage() {
  const { data: workflows, isLoading: wLoading } = useWorkflows()
  const { data: recentRuns, isLoading: rLoading } = useExecutions()

  const runStats = recentRuns?.reduce(
    (acc, run) => {
      if (run.status === 'SUCCESS') acc.success++
      else if (run.status === 'FAILED') acc.failed++
      else if (run.status === 'RUNNING') acc.running++
      return acc
    },
    { success: 0, failed: 0, running: 0 },
  )

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Dashboard</h1>
        <Link
          href="/workflows/new"
          className="flex items-center gap-1.5 rounded-md bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:opacity-90"
        >
          <Plus size={14} /> New Workflow
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard
          label="Total Workflows"
          value={wLoading ? '—' : String(workflows?.length ?? 0)}
        />
        <StatCard
          label="Running"
          value={rLoading ? '—' : String(runStats?.running ?? 0)}
          icon={<Loader2 size={14} className="animate-spin text-blue-500" />}
        />
        <StatCard
          label="Successful"
          value={rLoading ? '—' : String(runStats?.success ?? 0)}
          icon={<CheckCircle2 size={14} className="text-green-500" />}
        />
        <StatCard
          label="Failed"
          value={rLoading ? '—' : String(runStats?.failed ?? 0)}
          icon={<XCircle size={14} className="text-red-500" />}
        />
      </div>

      {/* Recent runs */}
      <section>
        <h2 className="text-sm font-medium mb-3">Recent Runs</h2>
        {rLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : (
          <div className="space-y-2">
            {(recentRuns ?? []).slice(0, 8).map((run) => (
              <Link
                key={run.run_id}
                href={`/workflows/${run.workflow_id}/runs/${run.run_id}`}
                className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm hover:bg-muted transition-colors"
              >
                <span className="font-mono text-xs text-muted-foreground truncate w-48">
                  {run.run_id}
                </span>
                <StatusBadge status={run.status} />
                <span className="text-xs text-muted-foreground hidden sm:block">
                  {new Date(run.started_at).toLocaleString()}
                </span>
              </Link>
            ))}
            {(recentRuns?.length ?? 0) === 0 && (
              <p className="text-sm text-muted-foreground">No runs yet.</p>
            )}
          </div>
        )}
      </section>
    </div>
  )
}

function StatCard({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border p-4">
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <span className="text-2xl font-semibold">{value}</span>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    SUCCESS: 'bg-green-100 text-green-700',
    FAILED: 'bg-red-100 text-red-700',
    RUNNING: 'bg-blue-100 text-blue-700',
    PENDING: 'bg-gray-100 text-gray-600',
    CANCELLED: 'bg-yellow-100 text-yellow-700',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[status] ?? 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  )
}
