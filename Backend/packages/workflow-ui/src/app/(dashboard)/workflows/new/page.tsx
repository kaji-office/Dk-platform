// ─────────────────────────────────────────────────────────────────────────────
// ChatPage — /workflows/new
// Chat-first workflow creation: chat panel (380px) + canvas preview
// From docs/frontend/handover.md §8 module #4, chat-module.md §1
// ─────────────────────────────────────────────────────────────────────────────

'use client'

import { ChatPanel } from '@/components/chat/ChatPanel'
import { WorkflowCanvas } from '@/components/builder/WorkflowCanvas'
import { useWorkflowStore } from '@/stores/workflowStore'

export default function ChatPage() {
  const nodes = useWorkflowStore((s) => s.nodes)
  const hasCanvas = nodes.length > 0

  return (
    // Full-height layout overriding default dashboard padding
    <div className="absolute inset-0 flex">
      {/* Chat panel — fixed 380px, collapsible */}
      <ChatPanel />

      {/* Canvas — fills remaining space; shows placeholder until workflow generated */}
      <div className="flex-1 min-w-0 relative">
        {hasCanvas ? (
          <WorkflowCanvas />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            Workflow preview will appear here once generated.
          </div>
        )}
      </div>
    </div>
  )
}
