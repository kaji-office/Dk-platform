'use client'

import type { ConversationPhase } from '@/types/chat'

const PHASE_CONFIG: Record<ConversationPhase, { label: string; color: string }> = {
  GATHERING:   { label: 'Gathering',   color: 'bg-gray-200 text-gray-600' },
  CLARIFYING:  { label: 'Clarifying',  color: 'bg-yellow-100 text-yellow-700' },
  FINALIZING:  { label: 'Finalizing',  color: 'bg-blue-100 text-blue-600' },
  GENERATING:  { label: 'Generating',  color: 'bg-purple-100 text-purple-600' },
  COMPLETE:    { label: 'Complete',    color: 'bg-green-100 text-green-600' },
}

export function PhaseIndicator({ phase }: { phase: ConversationPhase }) {
  const cfg = PHASE_CONFIG[phase]
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${cfg.color}`}>
      {cfg.label}
    </span>
  )
}
