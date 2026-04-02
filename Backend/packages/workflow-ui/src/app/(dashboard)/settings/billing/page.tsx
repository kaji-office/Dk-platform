'use client'

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import type { UsageSummary, ApiResponse } from '@/types/api'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'

export default function BillingPage() {
  const { data: usage, isLoading } = useQuery({
    queryKey: ['usage'],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<UsageSummary>>('/api/v1/usage')
      return data.data
    },
  })

  const chartData = usage
    ? Object.entries(usage.breakdown_by_node_type).map(([type, stats]) => ({
        name: type.replace('Node', ''),
        executions: stats.count,
        tokens: stats.tokens,
      }))
    : []

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-lg font-semibold">Usage & Billing</h1>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {usage && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <SummaryCard label="Total Runs" value={String(usage.total_executions)} />
            <SummaryCard label="Successful" value={String(usage.successful_executions)} />
            <SummaryCard label="Failed" value={String(usage.failed_executions)} />
            <SummaryCard
              label="Est. Cost"
              value={`$${usage.estimated_cost_usd.toFixed(4)}`}
            />
          </div>

          {/* Executions by node type */}
          <section>
            <h2 className="text-sm font-medium mb-3">Executions by Node Type</h2>
            <div className="rounded-lg border border-border p-4 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="executions" fill="#6366f1" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          {/* LLM token spend */}
          <section>
            <h2 className="text-sm font-medium mb-3">LLM Tokens by Node Type</h2>
            <div className="rounded-lg border border-border p-4 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="tokens" fill="#8b5cf6" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
        </>
      )}
    </div>
  )
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-2xl font-semibold mt-1">{value}</p>
    </div>
  )
}
