// ─────────────────────────────────────────────────────────────────────────────
// ChatPanel — main chat shell
// Spec: docs/frontend/chat-module.md
// Layout: 380px expanded / 48px collapsed icon strip
// ─────────────────────────────────────────────────────────────────────────────

'use client'

import { useCallback } from 'react'
import { MessageSquare, ChevronLeft, ChevronRight } from 'lucide-react'
import { useChatStore } from '@/stores/chatStore'
import { useCreateChatSession, useSendMessage } from '@/api/chat'
import { useChatWebSocket } from '@/hooks/useChatWebSocket'
import { MessageThread } from './MessageThread'
import { ChatInputBar } from './ChatInputBar'
import { ClarificationCard } from './ClarificationCard'
import { PhaseIndicator } from './PhaseIndicator'
import { apiClient } from '@/api/client'
import type { ChatMessageResponse } from '@/types/chat'
import type { ApiResponse } from '@/types/api'

export function ChatPanel() {
  const {
    sessionId,
    isPanelCollapsed,
    clarificationBlock,
    phase,
    togglePanel,
    setSessionId,
    appendMessage,
    applyMessageResponse,
  } = useChatStore()

  const createSession = useCreateChatSession()
  // Send message hook — only usable once sessionId is known
  // Hook is always called (rules of hooks), but mutation is disabled when no session
  const sendMsgMutation = useSendMessage(sessionId ?? '')

  // After WS "response" event: fetch full REST payload to get clarification/workflow
  const handleWsResponse = useCallback(
    async (event: { type: 'response'; phase: 'COMPLETE'; message: string; workflow_id: string | null }) => {
      if (!sessionId) return
      try {
        const { data } = await apiClient.get<ApiResponse<ChatMessageResponse>>(
          `/api/v1/chat/sessions/${sessionId}`,
        )
        applyMessageResponse(data.data)
      } catch (err) {
        console.error('[ChatPanel] failed to fetch session after WS response', err)
      }
    },
    [sessionId, applyMessageResponse],
  )

  const { sendMessage: sendWsMessage } = useChatWebSocket(sessionId, {
    onResponse: handleWsResponse,
  })

  async function handleSend(content: string) {
    // Create session on first message
    let sid = sessionId
    if (!sid) {
      const result = await createSession.mutateAsync()
      sid = result.session_id
      setSessionId(sid)
    }

    // Optimistically add user message
    appendMessage({ id: `u_${Date.now()}`, role: 'user', content, ts: new Date().toISOString() })

    // Prefer WS for real-time UX; also call REST for reliable state sync
    sendWsMessage(content)
    const response = await sendMsgMutation.mutateAsync(content)
    applyMessageResponse(response)
  }

  if (isPanelCollapsed) {
    return (
      <div className="w-12 shrink-0 border-r border-border flex flex-col items-center py-3 gap-3">
        <button onClick={togglePanel} title="Open chat" className="p-1 rounded hover:bg-muted">
          <MessageSquare size={18} />
        </button>
      </div>
    )
  }

  return (
    <div className="w-96 shrink-0 border-r border-border flex flex-col bg-background">
      {/* Header */}
      <div className="h-12 border-b border-border flex items-center justify-between px-3">
        <div className="flex items-center gap-2">
          <MessageSquare size={16} />
          <span className="text-sm font-medium">Chat</span>
        </div>
        <div className="flex items-center gap-2">
          <PhaseIndicator phase={phase} />
          <button onClick={togglePanel} className="p-1 rounded hover:bg-muted">
            <ChevronLeft size={15} />
          </button>
        </div>
      </div>

      {/* Message thread — scrollable */}
      <MessageThread />

      {/* Clarification form */}
      {clarificationBlock && phase === 'CLARIFYING' && (
        <ClarificationCard onSubmit={handleSend} />
      )}

      {/* Input bar */}
      <ChatInputBar onSend={handleSend} disabled={createSession.isPending || sendMsgMutation.isPending} />
    </div>
  )
}
