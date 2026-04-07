// ─────────────────────────────────────────────────────────────────────────────
// Chat store — full spec from docs/frontend/chat-module.md §4
//
// Coupling to workflowStore: when phase reaches COMPLETE and workflow_preview
// is available, this store calls workflowStore.loadFromDefinition().
// That's the only coupling point between the two stores.
// ─────────────────────────────────────────────────────────────────────────────

import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import type {
  ConversationPhase,
  ChatMessage,
  ClarificationBlock,
  RequirementSpec,
  ChatMessageResponse,
} from '@/types/chat'
import type { WorkflowDefinition } from '@/types/api'

interface ChatStore {
  // Session
  sessionId: string | null
  phase: ConversationPhase
  clarificationRound: number

  // Messages
  messages: ChatMessage[]
  streamingContent: string
  isStreaming: boolean

  // Clarification
  clarificationBlock: ClarificationBlock | null
  clarificationAnswers: Record<string, string>

  // Requirements
  requirementSpec: RequirementSpec | null

  // Workflow
  workflowPreview: WorkflowDefinition | null
  workflowId: string | null

  // UI
  isPanelCollapsed: boolean

  // Actions
  setSessionId: (id: string) => void
  appendMessage: (msg: ChatMessage) => void
  setStreaming: (content: string) => void
  finalizeStreaming: () => void
  applyMessageResponse: (response: ChatMessageResponse) => void
  setClarificationAnswer: (questionId: string, answer: string) => void
  formatAnswersForSubmission: () => string
  togglePanel: () => void
  reset: () => void
}

const initialState = {
  sessionId: null,
  phase: 'GATHERING' as ConversationPhase,
  clarificationRound: 0,
  messages: [],
  streamingContent: '',
  isStreaming: false,
  clarificationBlock: null,
  clarificationAnswers: {},
  requirementSpec: null,
  workflowPreview: null,
  workflowId: null,
  isPanelCollapsed: false,
}

export const useChatStore = create<ChatStore>()(
  devtools(
    (set, get) => ({
      ...initialState,

      setSessionId: (id) =>
        set({ sessionId: id }, false, 'chat/setSessionId'),

      appendMessage: (msg) =>
        set(
          (s) => ({ messages: [...s.messages, msg] }),
          false,
          'chat/appendMessage',
        ),

      // Called on each WS token chunk (streaming text)
      setStreaming: (content) =>
        set(
          { streamingContent: content, isStreaming: true },
          false,
          'chat/setStreaming',
        ),

      // Called when WS emits "response" — moves streaming content into messages
      finalizeStreaming: () =>
        set(
          (s) => ({
            isStreaming: false,
            streamingContent: '',
            // Streaming content is already committed via appendMessage from REST response
          }),
          false,
          'chat/finalizeStreaming',
        ),

      // Apply the full REST response after a message round-trip
      applyMessageResponse: (response) => {
        set(
          (s) => {
            const assistantMsg: ChatMessage = {
              id: `msg_${Date.now()}`,
              role: 'assistant',
              content: response.message,
              ts: new Date().toISOString(),
            }

            // When workflow is ready, load it into the canvas store
            if (response.phase === 'COMPLETE' && response.workflow_preview) {
              // Lazy import to avoid circular dep at module load
              const { useWorkflowStore } = require('./workflowStore')
              useWorkflowStore.getState().loadFromDefinition(
                response.workflow_preview,
                response.workflow_id ?? undefined,
              )
            }

            return {
              phase: response.phase,
              messages: [...s.messages, assistantMsg],
              clarificationBlock: response.clarification,
              requirementSpec: response.requirement_spec ?? s.requirementSpec,
              workflowPreview: response.workflow_preview ?? s.workflowPreview,
              workflowId: response.workflow_id ?? s.workflowId,
              clarificationRound:
                response.clarification ? s.clarificationRound + 1 : s.clarificationRound,
            }
          },
          false,
          'chat/applyMessageResponse',
        )
      },

      setClarificationAnswer: (questionId, answer) =>
        set(
          (s) => ({
            clarificationAnswers: { ...s.clarificationAnswers, [questionId]: answer },
          }),
          false,
          'chat/setClarificationAnswer',
        ),

      // Formats all clarification answers into a single user message string
      formatAnswersForSubmission: () => {
        const { clarificationBlock, clarificationAnswers } = get()
        if (!clarificationBlock) return ''
        return clarificationBlock.questions
          .map((q) => `${q.question}: ${clarificationAnswers[q.id] ?? ''}`)
          .join('\n')
      },

      togglePanel: () =>
        set(
          (s) => ({ isPanelCollapsed: !s.isPanelCollapsed }),
          false,
          'chat/togglePanel',
        ),

      reset: () => set(initialState, false, 'chat/reset'),
    }),
    { name: 'ChatStore' },
  ),
)
