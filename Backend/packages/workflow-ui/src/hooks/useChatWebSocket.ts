// ─────────────────────────────────────────────────────────────────────────────
// useChatWebSocket — lightweight phase signal stream for chat
//
// Endpoint: /api/v1/chat/sessions/ws/chat/{session_id}?token=<jwt>
//
// The WS only delivers:  status | phase | response
// Rich payload (clarification questions, WorkflowDefinition) always comes
// from REST GET /sessions/{id} — fetch it after receiving "response" event.
// (from docs/frontend/handover.md §5)
//
// Reconnect strategy: exponential backoff up to 30s, max 5 attempts.
// ─────────────────────────────────────────────────────────────────────────────

'use client'

import { useEffect, useRef, useCallback } from 'react'
import { buildWsUrl } from '@/api/client'
import { useChatStore } from '@/stores/chatStore'
import type { ChatWsEvent } from '@/types/chat'

interface Options {
  // Called when WS emits "response" — use to trigger REST fetch for full payload
  onResponse: (event: Extract<ChatWsEvent, { type: 'response' }>) => void
  onPhaseChange?: (phase: string) => void
}

export function useChatWebSocket(sessionId: string | null, options: Options) {
  const ws = useRef<WebSocket | null>(null)
  const reconnectAttempts = useRef(0)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()
  const { onResponse, onPhaseChange } = options

  const setStreaming = useChatStore((s) => s.setStreaming)
  const finalizeStreaming = useChatStore((s) => s.finalizeStreaming)

  const connect = useCallback(() => {
    if (!sessionId || typeof window === 'undefined') return

    const url = buildWsUrl(`/api/v1/chat/sessions/ws/chat/${sessionId}`)
    const socket = new WebSocket(url)
    ws.current = socket

    socket.onopen = () => {
      reconnectAttempts.current = 0
    }

    socket.onmessage = (e: MessageEvent) => {
      let event: ChatWsEvent
      try {
        event = JSON.parse(e.data as string) as ChatWsEvent
      } catch {
        return
      }

      switch (event.type) {
        case 'status':
          setStreaming('') // reset streaming buffer, AI is processing
          break

        case 'phase':
          onPhaseChange?.(event.phase)
          break

        case 'response':
          finalizeStreaming()
          onResponse(event) // caller fetches REST for full payload
          break
      }
    }

    socket.onerror = () => {
      console.warn('[ChatWS] error')
    }

    socket.onclose = (e) => {
      if (e.code === 4001) {
        console.warn('[ChatWS] unauthorized')
        return // don't reconnect
      }
      if (e.code === 1000) return // normal close

      // Exponential backoff reconnect
      const maxAttempts = 5
      if (reconnectAttempts.current < maxAttempts) {
        const delay = Math.min(1000 * 2 ** reconnectAttempts.current, 30_000)
        reconnectAttempts.current += 1
        reconnectTimer.current = setTimeout(connect, delay)
      }
    }
  }, [sessionId, onResponse, onPhaseChange, setStreaming, finalizeStreaming])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      ws.current?.close(1000)
    }
  }, [connect])

  // Send a message over the WebSocket (used instead of REST for real-time UX)
  const sendMessage = useCallback((content: string) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'message', content }))
    }
  }, [])

  return { sendMessage }
}
