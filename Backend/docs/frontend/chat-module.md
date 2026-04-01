### G-6 — Chat UI — Conversation Panel + DAG Preview

**Full spec:** `docs/frontend/chat-module.md`
**Foundation:** `docs/frontend/overview.md` (Next.js 14, React Flow v12, Zustand, shadcn/ui)

**New files added to existing `packages/workflow-ui/src/`:**
```
app/(dashboard)/workflows/new/page.tsx    ← ChatPage (route: /workflows/new)
components/chat/
  ChatPanel.tsx          PhaseIndicator.tsx    TypingIndicator.tsx
  MessageThread.tsx      ClarificationCard.tsx  PromptSuggestions.tsx
  MessageBubble.tsx      QuestionWidget.tsx     ChatInputBar.tsx
  StreamingText.tsx      RequirementProgress.tsx
components/nodes/ChatGeneratedNode.tsx    ← React Flow node for AI-generated workflows
stores/chatStore.ts                       ← Zustand chat state (see spec §4)
api/chat.ts                               ← TanStack Query hooks (see spec §5)
hooks/useChatWebSocket.ts                 ← WebSocket token streaming (see spec §6)
types/chat.ts                             ← TypeScript interfaces
```

**Layout:** Chat panel (380px, collapsible to 48px) left of full-height canvas. Config panel overlaps canvas from right (does not shrink canvas).

**Tech choices locked:**
- `useChatStore` (Zustand) — owns all chat state; `workflowStore.loadFromDefinition()` called when workflow ready
- `useChatWebSocket` — native WebSocket, reconnects with 3s backoff; routes `token | done | phase_change | workflow_ready` events
- `ChatGeneratedNode` — coloured header from `ui_config.color`, Lucide icon from `ui_config.icon`, config preview pills, conditional port handles based on `is_terminal`
- `ClarificationCard` — React Hook Form; question type → widget: `text→Textarea`, `select→Select`, `multiselect→CheckboxGroup`, `boolean→Switch`, `number→Input`
- Canvas edits debounced 1s → `PUT /chat/sessions/{id}/workflow` → validation errors highlight nodes red, suggestions render as dismissible toasts
- Empty canvas shows prompt suggestion chips (4 starters); clicking one sends the prompt and creates a session automatically

**Acceptance criteria:**
- [ ] WebSocket token streaming renders text incrementally — no full re-render
- [ ] `ClarificationCard` renders correct input widget per `input_type`
- [ ] Submitting all clarification answers via form auto-sends a message with answers formatted
- [ ] `RequirementProgressBar` shows correct filled/missing fields from `requirement_spec`
- [ ] DAG canvas renders all nodes with correct colour, icon, and label from `ui_config`
- [ ] Node position `{x, y}` from `WorkflowDefinition` is honoured — no re-layout on render
- [ ] Dragging a node updates its position, triggers debounced `PUT /workflow`
- [ ] `validation_errors` from backend highlight the affected node/edge in red
- [ ] `suggestions` toast appears and is dismissible
- [ ] `EditWorkflowButton` navigates to `/workflows/{workflow_id}/edit` (full canvas — F-2)
- [ ] Responsive: ChatPanel stacks above WorkflowPreviewPanel on screens < 1024px
- [ ] Phase transitions animate (fade) in `PhaseIndicator`


# Frontend — Chat-Driven Workflow Builder (G-6 Spec)

> Extends `docs/frontend/overview.md`. Assumes Next.js 14 App Router, React Flow v12,
> Zustand, TanStack Query v5, Tailwind CSS, shadcn/ui, Framer Motion, Lucide React.

---

## 1. Where Chat Lives in the App

### Route

```
/workflows/new          → ChatPage (chat-first creation flow)
/workflows/[id]         → WorkflowEditorPage (existing canvas editor — chat accessible as panel)
```

### Layout: Split-Screen Editor

```
┌─────────────────────────────────────────────────────────────────────┐
│  TopBar: [← Workflows]  [workflow name]  [⚡ Run] [💾 Save] [···]  │
├────────────────┬────────────────────────────────────┬───────────────┤
│                │                                    │               │
│   Chat Panel   │      Workflow Canvas (React Flow)  │  Config Panel │
│   (collapsed   │                                    │  (slides in   │
│    or 380px)   │   Nodes + edges rendered here      │   on select)  │
│                │                                    │               │
│   [≡] toggle   │   Grid bg, zoom/pan, minimap       │               │
│                │                                    │               │
└────────────────┴────────────────────────────────────┴───────────────┘
```

- Chat panel: **fixed 380px**, collapsible to **48px icon strip** via toggle
- Canvas: fills remaining horizontal space
- Config panel: **380px overlay** from right, does NOT shrink canvas — it overlaps with 8px shadow
- On screens < 1024px: Chat stacks above Canvas (vertical split)

---

## 2. New Files Added to Existing Structure

```
packages/workflow-ui/src/
│
├── app/(dashboard)/
│   └── workflows/
│       └── new/
│           └── page.tsx              ← NEW: ChatPage (chat-first creation)
│
├── components/
│   └── chat/                         ← NEW: entire directory
│       ├── ChatPanel.tsx             ← Panel shell + toggle collapse
│       ├── MessageThread.tsx         ← Scrollable message history
│       ├── MessageBubble.tsx         ← User / assistant bubble
│       ├── StreamingText.tsx         ← WebSocket token consumer
│       ├── TypingIndicator.tsx       ← "AI is thinking..." animation
│       ├── ClarificationCard.tsx     ← Renders ClarificationBlock questions
│       ├── QuestionWidget.tsx        ← text | select | multiselect | boolean | number
│       ├── RequirementProgress.tsx   ← Field completion progress bar
│       ├── PromptSuggestions.tsx     ← Suggested starter prompts
│       ├── PhaseIndicator.tsx        ← GATHERING → CLARIFYING → GENERATING → COMPLETE
│       ├── ChatInputBar.tsx          ← Textarea + send button + attach
│       └── index.ts                  ← re-exports
│
├── stores/
│   └── chatStore.ts                  ← NEW: Zustand chat state
│
├── api/
│   └── chat.ts                       ← NEW: TanStack Query hooks for chat endpoints
│
└── hooks/
    └── useChatWebSocket.ts           ← NEW: WebSocket hook for token streaming
```

---

## 3. Type Definitions

```typescript
// types/chat.ts

export type ConversationPhase =
  | 'GATHERING'
  | 'CLARIFYING'
  | 'FINALIZING'
  | 'GENERATING'
  | 'COMPLETE'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  ts: string
}

export interface ClarificationQuestion {
  id: string
  question: string
  input_type: 'text' | 'select' | 'multiselect' | 'boolean' | 'number'
  options: string[]
  hint?: string
  required: boolean
  maps_to_field?: string
}

export interface ClarificationBlock {
  type: 'clarification'
  questions: ClarificationQuestion[]
}

export interface RequirementSpec {
  goal?: string
  trigger_type?: 'manual' | 'scheduled' | 'webhook'
  trigger_config?: Record<string, unknown>
  input_sources?: string[]
  processing_steps?: Array<{
    description: string
    suggested_node_type?: string
    config_hints?: Record<string, unknown>
  }>
  integrations?: string[]
  output_format?: string
  constraints?: Record<string, unknown>
}

export interface ChatMessageResponse {
  session_id: string
  phase: ConversationPhase
  reply: string
  clarification: ClarificationBlock | null
  requirement_spec: RequirementSpec | null
  workflow_preview: WorkflowDefinition | null
  workflow_id: string | null
}

export interface ChatSession {
  session_id: string
  phase: ConversationPhase
  clarification_round: number
  generated_workflow_id: string | null
  created_at: string
  updated_at: string
}

// WebSocket events from /ws/chat/{session_id}
export type ChatWsEvent =
  | { type: 'token'; content: string }
  | { type: 'done'; phase: ConversationPhase; full_response: ChatMessageResponse }
  | { type: 'phase_change'; from: ConversationPhase; to: ConversationPhase }
  | { type: 'workflow_ready'; workflow_id: string; workflow_preview: WorkflowDefinition }
```

---

## 4. Zustand Chat Store

```typescript
// stores/chatStore.ts

import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import type { ChatMessage, ChatMessageResponse, ClarificationBlock,
               ConversationPhase, RequirementSpec, WorkflowDefinition } from '@/types/chat'

interface ChatStore {
  // ── Session ──────────────────────────────────────────────────────────
  sessionId: string | null
  phase: ConversationPhase
  clarificationRound: number

  // ── Messages ─────────────────────────────────────────────────────────
  messages: ChatMessage[]
  streamingContent: string      // accumulates WebSocket tokens in real-time
  isStreaming: boolean

  // ── Clarification ─────────────────────────────────────────────────────
  clarificationBlock: ClarificationBlock | null
  clarificationAnswers: Record<string, string>  // { question_id → answer }

  // ── Requirements ──────────────────────────────────────────────────────
  requirementSpec: RequirementSpec | null

  // ── Workflow ───────────────────────────────────────────────────────────
  workflowPreview: WorkflowDefinition | null
  workflowId: string | null

  // ── UI ────────────────────────────────────────────────────────────────
  isPanelCollapsed: boolean
  inputValue: string

  // ── Actions ───────────────────────────────────────────────────────────
  initSession: (session: { session_id: string; phase: ConversationPhase }) => void
  appendUserMessage: (content: string) => void
  appendStreamToken: (token: string) => void
  commitStreamedMessage: (response: ChatMessageResponse) => void
  setClarificationAnswer: (questionId: string, answer: string) => void
  applyPhaseChange: (from: ConversationPhase, to: ConversationPhase) => void
  applyWorkflowReady: (workflowId: string, preview: WorkflowDefinition) => void
  setInputValue: (v: string) => void
  togglePanel: () => void
  reset: () => void
}

const REQUIRED_FIELDS: (keyof RequirementSpec)[] = [
  'goal', 'trigger_type', 'processing_steps', 'output_format'
]

export const useChatStore = create<ChatStore>()(
  devtools(
    (set, get) => ({
      sessionId: null,
      phase: 'GATHERING',
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
      inputValue: '',

      initSession: (session) =>
        set({ sessionId: session.session_id, phase: session.phase }),

      appendUserMessage: (content) =>
        set((s) => ({
          messages: [
            ...s.messages,
            { id: `msg_${Date.now()}`, role: 'user', content, ts: new Date().toISOString() },
          ],
          isStreaming: true,
          streamingContent: '',
          clarificationBlock: null,  // clear previous clarification
        })),

      appendStreamToken: (token) =>
        set((s) => ({ streamingContent: s.streamingContent + token })),

      commitStreamedMessage: (response) =>
        set((s) => ({
          messages: [
            ...s.messages,
            {
              id: `msg_${Date.now()}`,
              role: 'assistant',
              content: response.reply,
              ts: new Date().toISOString(),
            },
          ],
          streamingContent: '',
          isStreaming: false,
          phase: response.phase,
          clarificationBlock: response.clarification,
          requirementSpec: response.requirement_spec ?? s.requirementSpec,
          workflowPreview: response.workflow_preview ?? s.workflowPreview,
          workflowId: response.workflow_id ?? s.workflowId,
        })),

      setClarificationAnswer: (questionId, answer) =>
        set((s) => ({
          clarificationAnswers: { ...s.clarificationAnswers, [questionId]: answer },
        })),

      applyPhaseChange: (from, to) => set({ phase: to }),

      applyWorkflowReady: (workflowId, preview) =>
        set({ workflowId, workflowPreview: preview, phase: 'COMPLETE' }),

      setInputValue: (v) => set({ inputValue: v }),

      togglePanel: () => set((s) => ({ isPanelCollapsed: !s.isPanelCollapsed })),

      reset: () =>
        set({
          sessionId: null, phase: 'GATHERING', clarificationRound: 0,
          messages: [], streamingContent: '', isStreaming: false,
          clarificationBlock: null, clarificationAnswers: {},
          requirementSpec: null, workflowPreview: null, workflowId: null,
          inputValue: '',
        }),
    }),
    { name: 'ChatStore' }
  )
)

// Derived selector: which RequirementSpec fields are still missing
export const useMissingFields = () =>
  useChatStore((s) => REQUIRED_FIELDS.filter((f) => !s.requirementSpec?.[f]))
```

---

## 5. API Hooks (TanStack Query)

```typescript
// api/chat.ts

import { useMutation, useQuery } from '@tanstack/react-query'
import { apiClient } from './client'
import type { ChatMessageResponse, ChatSession, WorkflowDefinition } from '@/types/chat'

// ── Session management ───────────────────────────────────────────────

export const useCreateChatSession = () =>
  useMutation({
    mutationFn: (title?: string) =>
      apiClient.post<ChatSession>('/chat/sessions', { title }).then((r) => r.data),
  })

export const useChatSession = (sessionId: string | null) =>
  useQuery({
    queryKey: ['chat-session', sessionId],
    queryFn: () =>
      apiClient.get<ChatSession>(`/chat/sessions/${sessionId}`).then((r) => r.data),
    enabled: !!sessionId,
  })

export const useChatSessions = () =>
  useQuery({
    queryKey: ['chat-sessions'],
    queryFn: () =>
      apiClient.get<{ items: ChatSession[]; total: number }>('/chat/sessions').then((r) => r.data),
  })

// ── Message send (REST fallback when WebSocket unavailable) ──────────

export const useSendMessage = (sessionId: string) =>
  useMutation({
    mutationFn: (content: string) =>
      apiClient
        .post<ChatMessageResponse>(`/chat/sessions/${sessionId}/message`, { content })
        .then((r) => r.data),
  })

// ── Force generate ────────────────────────────────────────────────────

export const useForceGenerate = (sessionId: string) =>
  useMutation({
    mutationFn: () =>
      apiClient
        .post<ChatMessageResponse>(`/chat/sessions/${sessionId}/generate`)
        .then((r) => r.data),
  })

// ── Workflow update (after canvas edits) ─────────────────────────────

export const useUpdateChatWorkflow = (sessionId: string) =>
  useMutation({
    mutationFn: (payload: {
      updated_nodes: Record<string, unknown>
      updated_edges: unknown[]
      ui_metadata: unknown
    }) =>
      apiClient
        .put(`/chat/sessions/${sessionId}/workflow`, payload)
        .then((r) => r.data),
  })
```

---

## 6. WebSocket Hook

```typescript
// hooks/useChatWebSocket.ts

import { useEffect, useRef, useCallback } from 'react'
import { useChatStore } from '@/stores/chatStore'
import { useWorkflowStore } from '@/stores/workflowStore'
import type { ChatWsEvent } from '@/types/chat'

export function useChatWebSocket(sessionId: string | null) {
  const ws = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()

  const {
    appendStreamToken,
    commitStreamedMessage,
    applyPhaseChange,
    applyWorkflowReady,
  } = useChatStore()

  const { loadFromDefinition } = useWorkflowStore()

  const connect = useCallback(() => {
    if (!sessionId) return
    const url = `${process.env.NEXT_PUBLIC_WS_URL}/ws/chat/${sessionId}`
    ws.current = new WebSocket(url)

    ws.current.onmessage = (ev) => {
      const event: ChatWsEvent = JSON.parse(ev.data)

      switch (event.type) {
        case 'token':
          appendStreamToken(event.content)
          break

        case 'done':
          commitStreamedMessage(event.full_response)
          // If workflow was generated, load it into the canvas store
          if (event.full_response.workflow_preview) {
            loadFromDefinition(event.full_response.workflow_preview)
          }
          break

        case 'phase_change':
          applyPhaseChange(event.from, event.to)
          break

        case 'workflow_ready':
          applyWorkflowReady(event.workflow_id, event.workflow_preview)
          loadFromDefinition(event.workflow_preview)
          break
      }
    }

    ws.current.onclose = () => {
      // Reconnect with exponential backoff (max 30s)
      reconnectTimer.current = setTimeout(connect, 3000)
    }
  }, [sessionId, appendStreamToken, commitStreamedMessage, applyPhaseChange, applyWorkflowReady, loadFromDefinition])

  useEffect(() => {
    connect()
    return () => {
      ws.current?.close(1000)
      clearTimeout(reconnectTimer.current)
    }
  }, [connect])
}
```

---

## 7. Component Specifications

### 7.1 ChatPanel

```
┌─────────────────────────────────────────────────────┐
│  💬 AI Assistant                      [phase badge] [≡]│
├─────────────────────────────────────────────────────┤
│  RequirementProgress ──────────────────────────────  │
│  ● Goal ✓  ● Trigger ✓  ● Steps ?  ● Output ?        │
├─────────────────────────────────────────────────────┤
│                                                      │
│  MessageThread (overflow-y: scroll, flex-col)        │
│                                                      │
│  [User] Create a lead scoring workflow               │
│                                                      │
│  [AI]  I can help with that! To design this          │
│        workflow, I need a few details...             │
│                                                      │
│  ┌─ ClarificationCard ─────────────────────────────┐ │
│  │ Q1: What triggers this workflow?                 │ │
│  │  ○ Manual  ● Webhook  ○ Schedule                 │ │
│  │                                                  │ │
│  │ Q2: Where do the leads come from?                │ │
│  │  [Salesforce CRM                          ▼]     │ │
│  │                                                  │ │
│  │            [Submit Answers →]                    │ │
│  └──────────────────────────────────────────────────┘ │
│                                                      │
│  TypingIndicator (when isStreaming)                  │
│  [●●●]  AI is thinking...                            │
│                                                      │
├─────────────────────────────────────────────────────┤
│  ChatInputBar                                        │
│  ┌──────────────────────────────────────┐ [⬆ Send] │
│  │ Describe your workflow...            │           │
│  └──────────────────────────────────────┘           │
│  [⚡ Force Generate]   [📎 Attach]                   │
└─────────────────────────────────────────────────────┘
```

**Collapsed state (48px strip):**
```
┌────┐
│ 💬 │  ← click to expand
│    │
│ 3  │  ← unread indicator (message count since collapse)
└────┘
```

### 7.2 PhaseIndicator

```typescript
const PHASE_CONFIG: Record<ConversationPhase, { label: string; color: string; icon: LucideIcon }> = {
  GATHERING:   { label: 'Gathering',   color: 'bg-slate-100 text-slate-600',   icon: MessageCircle },
  CLARIFYING:  { label: 'Clarifying',  color: 'bg-amber-100 text-amber-700',   icon: HelpCircle },
  FINALIZING:  { label: 'Finalizing',  color: 'bg-blue-100 text-blue-700',     icon: CheckCircle2 },
  GENERATING:  { label: 'Generating',  color: 'bg-purple-100 text-purple-700', icon: Sparkles },
  COMPLETE:    { label: 'Complete',    color: 'bg-green-100 text-green-700',   icon: CheckCircle },
}
// Renders as animated pill badge next to panel title
// Framer Motion: fade + slide on phase change
```

### 7.3 ClarificationCard

```typescript
// Renders the ClarificationBlock from the API response
// Each question → QuestionWidget based on input_type

function ClarificationCard({ block, onSubmit }: {
  block: ClarificationBlock
  onSubmit: (answers: Record<string, string>) => void
}) {
  // React Hook Form manages all question answers
  // Submit compiles answers into a formatted message:
  // "Q1: Webhook  Q2: Salesforce CRM" → sent as next user message
}
```

### 7.4 QuestionWidget

```typescript
function QuestionWidget({ question, value, onChange }: QuestionWidgetProps) {
  switch (question.input_type) {
    case 'select':
      return (
        <Select value={value} onValueChange={onChange}>
          {question.options.map(o => <SelectItem key={o} value={o}>{o}</SelectItem>)}
        </Select>
      )
    case 'multiselect':
      return <CheckboxGroup options={question.options} value={value} onChange={onChange} />
    case 'boolean':
      return <Switch checked={value === 'true'} onCheckedChange={v => onChange(String(v))} />
    case 'number':
      return <Input type="number" value={value} onChange={e => onChange(e.target.value)} />
    default: // 'text'
      return (
        <Textarea
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={question.hint}
          rows={2}
        />
      )
  }
}
```

### 7.5 RequirementProgress

```typescript
// Shows pill badges for each required field:
// Filled (green check) → goal, trigger_type captured
// Missing (grey dot)  → processing_steps, output_format not yet captured

const FIELD_LABELS: Record<string, string> = {
  goal: 'Goal',
  trigger_type: 'Trigger',
  processing_steps: 'Steps',
  output_format: 'Output',
}

// Progress bar: (filled / total) * 100 width
// Example: Goal ✓ | Trigger ✓ | Steps · | Output ·  → 50%
```

### 7.6 StreamingText

```typescript
// Renders streamingContent from chatStore while isStreaming = true
// Uses a blinking cursor ▌ appended after content
// When isStreaming → false, renders the committed message bubble instead

function StreamingText() {
  const { streamingContent, isStreaming } = useChatStore()
  if (!isStreaming) return null
  return (
    <div className="rounded-2xl bg-white border border-slate-200 px-4 py-3 max-w-[85%] self-start">
      <ReactMarkdown>{streamingContent}</ReactMarkdown>
      <span className="inline-block w-0.5 h-4 bg-slate-700 ml-0.5 animate-blink" />
    </div>
  )
}
```

### 7.7 PromptSuggestions (shown when session is new / messages empty)

```typescript
const SUGGESTIONS = [
  "Summarize PDFs and email the digest daily",
  "Score inbound leads from Salesforce and notify sales via Slack",
  "Monitor a GitHub repo and auto-create Jira tickets on new issues",
  "Run a weekly report from PostgreSQL and send to Google Sheets",
]
// Renders as clickable chips; clicking fills ChatInputBar and sends immediately
```

### 7.8 ChatInputBar

```typescript
function ChatInputBar() {
  const { inputValue, setInputValue, isStreaming } = useChatStore()
  const handleSend = () => { /* calls sendMessage action */ }

  return (
    <div className="border-t border-slate-200 p-3 space-y-2">
      <div className="flex gap-2">
        <Textarea
          value={inputValue}
          onChange={e => setInputValue(e.target.value)}
          placeholder="Describe your workflow or answer questions..."
          rows={2}
          className="resize-none flex-1"
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
          }}
          disabled={isStreaming}
        />
        <Button
          onClick={handleSend}
          disabled={!inputValue.trim() || isStreaming}
          size="icon"
          className="self-end"
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={/* useForceGenerate */}
          className="text-xs"
          disabled={isStreaming}
        >
          <Zap className="h-3 w-3 mr-1" /> Generate Now
        </Button>
      </div>
    </div>
  )
}
```

---

## 8. DAG Preview Canvas (Chat → React Flow Integration)

When the backend returns `workflow_preview`, the chat module calls `workflowStore.loadFromDefinition()`:

```typescript
// stores/workflowStore.ts — new action

loadFromDefinition: (definition: WorkflowDefinition) => {
  const rfNodes: Node[] = Object.entries(definition.nodes).map(([id, node]) => ({
    id,
    type: mapNodeTypeToRFComponent(node.type),  // 'TriggerNode' | 'AINode' | ...
    position: node.position ?? { x: 0, y: 0 },
    data: {
      label: node.ui_config?.node_type_label ?? node.type,
      config: node.config,
      uiConfig: node.ui_config,
      status: 'PENDING',
    },
  }))

  const rfEdges: Edge[] = definition.edges.map((e) => ({
    id: e.id,
    source: e.source_node_id,
    target: e.target_node_id,
    sourceHandle: e.source_port,
    targetHandle: e.target_port,
    type: 'smoothstep',
    animated: false,
    style: { stroke: '#94a3b8', strokeWidth: 2 },
  }))

  set({
    nodes: rfNodes,
    edges: rfEdges,
    workflowId: null,          // not yet saved
    isDirty: false,
    uiMetadata: definition.ui_metadata,
  })
}
```

The canvas is **always visible** on the right side. It shows:
- Empty state with dashed border + "Chat to generate your workflow" before generation
- Populated with nodes + edges after `workflow_ready`
- Fully editable after phase = COMPLETE (same canvas as F-2 editor)

---

## 9. ChatGeneratedNode (Custom React Flow Component)

```typescript
// components/nodes/ChatGeneratedNode.tsx
// Used for all nodes generated by chat, styled from ui_config

function ChatGeneratedNode({ data, selected }: NodeProps<ChatNodeData>) {
  const { uiConfig, label, config, status } = data
  const statusStyle = NODE_STATUS_STYLES[status ?? 'PENDING']

  return (
    <div
      className={cn(
        'rounded-xl border bg-white shadow-sm min-w-[180px] transition-all duration-150',
        selected && 'ring-2 ring-offset-2 ring-indigo-500',
        statusStyle.border,
      )}
    >
      {/* Coloured header band */}
      <div
        className="flex items-center gap-2 px-3 py-2 rounded-t-xl"
        style={{ backgroundColor: uiConfig?.color ?? '#6366f1' }}
      >
        <NodeIcon icon={uiConfig?.icon ?? 'box'} className="h-3.5 w-3.5 text-white" />
        <span className="text-xs font-semibold text-white truncate">{uiConfig?.node_type_label ?? label}</span>
        <span className={cn('ml-auto h-2 w-2 rounded-full', statusStyle.dot, statusStyle.animate)} />
      </div>

      {/* Config preview (first 2 non-empty fields) */}
      <div className="px-3 py-2 space-y-1">
        {getConfigPreviewPairs(config).map(([k, v]) => (
          <div key={k} className="flex gap-1.5 items-center">
            <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wide">{k}</span>
            <span className="text-[11px] text-slate-700 truncate max-w-[120px]">{String(v)}</span>
          </div>
        ))}
      </div>

      {/* React Flow port handles */}
      {!uiConfig?.is_terminal && (
        <>
          <Handle type="target" position={Position.Left} className="!h-3 !w-3 !border-2 !border-white !bg-slate-400" />
          <Handle type="source" position={Position.Right} className="!h-3 !w-3 !border-2 !border-white !bg-slate-400" />
        </>
      )}
      {uiConfig?.is_terminal && data.nodeType === 'output' && (
        <Handle type="target" position={Position.Left} className="!h-3 !w-3 !border-2 !border-white !bg-slate-400" />
      )}
      {uiConfig?.is_terminal && data.nodeType?.includes('trigger') && (
        <Handle type="source" position={Position.Right} className="!h-3 !w-3 !border-2 !border-white !bg-slate-400" />
      )}
    </div>
  )
}
```

---

## 10. ChatPage (Route: /workflows/new)

```typescript
// app/(dashboard)/workflows/new/page.tsx

export default function ChatPage() {
  const router = useRouter()
  const { workflowId, phase } = useChatStore()
  const createSession = useCreateChatSession()
  const { sessionId, initSession, reset } = useChatStore()

  useEffect(() => {
    reset()
    createSession.mutate(undefined, {
      onSuccess: (session) => initSession(session),
    })
    return () => reset()
  }, [])

  useChatWebSocket(sessionId)

  // When workflow is complete + user clicks "Edit in Canvas", navigate to editor
  const handleEditInCanvas = () => {
    if (workflowId) router.push(`/workflows/${workflowId}`)
  }

  return (
    <div className="flex h-[calc(100vh-56px)] overflow-hidden">
      {/* Left: Chat */}
      <ChatPanel className="border-r border-slate-200" />

      {/* Right: Live DAG preview */}
      <div className="flex-1 flex flex-col">
        <WorkflowPreviewToolbar
          phase={phase}
          workflowId={workflowId}
          onEditInCanvas={handleEditInCanvas}
        />
        <WorkflowCanvas
          readOnly={phase !== 'COMPLETE'}
          emptyStateMessage="Chat to generate your workflow →"
        />
      </div>
    </div>
  )
}
```

---

## 11. WorkflowPreviewToolbar

```
┌─────────────────────────────────────────────────────────────────────┐
│  [← Workflows]   ✦ AI-Generated Workflow     [phase badge]          │
│                                              [⚡ Edit in Canvas]    │
└─────────────────────────────────────────────────────────────────────┘
```

- Phase badge animates with Framer Motion on transition
- "Edit in Canvas" button: disabled until phase = COMPLETE, then navigates to `/workflows/{id}`
- "Regenerate" button: calls `/chat/sessions/{id}/generate` with loading spinner

---

## 12. Canvas Empty State

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                   │
│                    [sparkles icon — 48px]                         │
│                                                                   │
│              Your workflow will appear here                       │
│         Chat on the left to describe what you need               │
│                                                                   │
│         ── Suggested workflows ──────────────────────            │
│         [  Email Automation  ]  [  Lead Scoring  ]               │
│         [  Daily Report  ]      [  Data Pipeline  ]              │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

Clicking a suggestion chip fires the chat with that prompt and auto-creates a session.

---

## 13. Validation Feedback Loop (Edit → Backend → UI)

```typescript
// When user drags/deletes/connects in canvas:

onNodesChange / onEdgesChange
         │
         ▼ (debounced 1000ms)
useUpdateChatWorkflow.mutate({
  updated_nodes, updated_edges, ui_metadata: { layout: 'manual', ... }
})
         │
    ┌────┴────────┐
    │ valid: true │    valid: false
    │             │
    ▼             ▼
Save + show    Mark affected nodes/edges in red
suggestion     Show inline error toast:
toasts         "Cycle detected between node_2 → node_4"
               useWorkflowStore.markNodeError(nodeId, message)
               Canvas: node border turns red, tooltip shows error
```

---

## 14. Design Tokens (Tailwind Config)

```typescript
// tailwind.config.ts — additions for chat module

theme: {
  extend: {
    colors: {
      // Phase colours
      phase: {
        gathering:  { bg: '#f8fafc', text: '#475569', border: '#e2e8f0' },
        clarifying: { bg: '#fffbeb', text: '#92400e', border: '#fcd34d' },
        generating: { bg: '#f5f3ff', text: '#5b21b6', border: '#c4b5fd' },
        complete:   { bg: '#f0fdf4', text: '#166534', border: '#86efac' },
      },
      // Node category colours
      node: {
        ai:       '#6366f1',  // indigo
        data:     '#3b82f6',  // blue
        logic:    '#f97316',  // orange
        workflow: '#10b981',  // emerald
        trigger:  '#22c55e',  // green
      },
    },
    animation: {
      blink: 'blink 1s step-end infinite',
      'pulse-ring': 'pulse-ring 2s ease-in-out infinite',
    },
    keyframes: {
      blink: { '0%, 100%': { opacity: '1' }, '50%': { opacity: '0' } },
      'pulse-ring': {
        '0%, 100%': { boxShadow: '0 0 0 0px rgba(99, 102, 241, 0.4)' },
        '50%': { boxShadow: '0 0 0 8px rgba(99, 102, 241, 0)' },
      },
    },
  },
}
```

---

## 15. Interaction Design — Full Flow

```
1. User opens /workflows/new
   └─ Session created automatically
   └─ Empty canvas + prompt suggestions shown

2. User clicks a suggestion / types a query
   └─ appendUserMessage() → ChatInputBar disabled
   └─ WebSocket connects → tokens stream into StreamingText
   └─ TypingIndicator shown

3. Backend returns phase: CLARIFYING
   └─ commitStreamedMessage() → full assistant bubble rendered
   └─ ClarificationCard appears with QuestionWidget per question
   └─ PhaseIndicator animates: GATHERING → CLARIFYING

4. User fills clarification answers → clicks Submit
   └─ Answers formatted into message: "Trigger: Webhook, Source: Salesforce"
   └─ appendUserMessage() → sent as next /message call
   └─ Flow repeats until phase: GENERATING

5. Backend returns phase: GENERATING
   └─ PhaseIndicator: CLARIFYING → GENERATING
   └─ Canvas shows loading skeleton overlay

6. WebSocket emits workflow_ready
   └─ workflowStore.loadFromDefinition(preview)
   └─ Canvas renders nodes + edges with correct ui_config colors
   └─ Phase: COMPLETE
   └─ "Edit in Canvas" button activates

7. User drags node on canvas
   └─ node position updated in workflowStore
   └─ ui_metadata.layout = 'manual'
   └─ Debounced PUT /workflow → validation response
   └─ suggestions shown as toast (if any)

8. User clicks "Edit in Canvas"
   └─ router.push('/workflows/{id}')
   └─ WorkflowEditorPage loads with full palette, config panel, run button
```

---

## 16. Responsiveness

| Breakpoint | Layout |
|------------|--------|
| ≥ 1280px | Chat (380px) + Canvas (flex-1) side by side |
| 1024–1280px | Chat (320px) + Canvas (flex-1) |
| 768–1024px | Canvas full width; Chat as bottom drawer (240px, toggle) |
| < 768px | Chat full screen; Canvas via tab switch |

---

## 17. Accessibility

- All QuestionWidget inputs labelled via `aria-label` + `htmlFor`
- ClarificationCard has `role="form"` with descriptive `aria-label`
- StreamingText uses `aria-live="polite"` — screen readers read completions
- PhaseIndicator uses `aria-label="Conversation phase: {phase}"`
- Canvas nodes are not keyboard-navigable (React Flow limitation — acceptable for DAG builders)
- Keyboard shortcut: `Ctrl+Enter` submits ChatInputBar