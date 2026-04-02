// ─────────────────────────────────────────────────────────────────────────────
// useExecutionWebSocket — streams live node status events during a run
//
// Endpoint: /api/v1/ws/executions/{run_id}?token=<jwt>
//
// Usage: connect after triggering a run, disconnect on unmount or completion.
// The hook feeds events directly into workflowStore.applyWsEvent().
// Falls back to polling (usePollExecution) when WS is unavailable.
// ─────────────────────────────────────────────────────────────────────────────

'use client'

import { useEffect, useRef, useCallback } from 'react'
import { buildWsUrl } from '@/api/client'
import { useWorkflowStore } from '@/stores/workflowStore'
import type { ExecutionWsEvent } from '@/types/api'

interface Options {
  onTerminal?: (status: 'SUCCESS' | 'FAILED') => void
}

export function useExecutionWebSocket(runId: string | null, options: Options = {}) {
  const ws = useRef<WebSocket | null>(null)
  const applyWsEvent = useWorkflowStore((s) => s.applyWsEvent)
  const { onTerminal } = options

  const disconnect = useCallback(() => {
    ws.current?.close()
    ws.current = null
  }, [])

  useEffect(() => {
    if (!runId) return
    if (typeof window === 'undefined') return

    const url = buildWsUrl(`/api/v1/ws/executions/${runId}`)
    const socket = new WebSocket(url)
    ws.current = socket

    socket.onmessage = (e: MessageEvent) => {
      let event: ExecutionWsEvent
      try {
        event = JSON.parse(e.data as string) as ExecutionWsEvent
      } catch {
        return
      }

      applyWsEvent(event)

      // Notify caller when run reaches terminal state
      if (event.type === 'RUN_COMPLETED' && onTerminal) {
        onTerminal(event.status)
      }
    }

    socket.onerror = () => {
      // WS error — polling will take over via usePollExecution
      console.warn('[ExecutionWS] connection error, falling back to polling')
    }

    socket.onclose = (e) => {
      // Code 4001 = unauthorized (invalid/missing token)
      if (e.code === 4001) {
        console.warn('[ExecutionWS] unauthorized — token expired or missing')
      }
    }

    return () => {
      socket.close()
    }
  }, [runId, applyWsEvent, onTerminal])

  return { disconnect }
}
