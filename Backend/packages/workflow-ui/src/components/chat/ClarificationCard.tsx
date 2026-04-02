// ─────────────────────────────────────────────────────────────────────────────
// ClarificationCard — renders ClarificationBlock as a typed form
//
// Question widget mapping (from docs/frontend/handover.md §3.2):
//   text        → Textarea
//   select      → <select>
//   multiselect → checkbox group
//   boolean     → toggle switch
//   number      → number input
// ─────────────────────────────────────────────────────────────────────────────

'use client'

import { useForm } from 'react-hook-form'
import { useChatStore } from '@/stores/chatStore'
import type { ClarificationQuestion } from '@/types/chat'

interface Props {
  onSubmit: (formattedAnswers: string) => void
}

export function ClarificationCard({ onSubmit }: Props) {
  const { clarificationBlock, setClarificationAnswer, formatAnswersForSubmission } = useChatStore()
  const { register, handleSubmit } = useForm<Record<string, string | boolean | number>>()

  if (!clarificationBlock) return null

  function onFormSubmit(values: Record<string, string | boolean | number>) {
    Object.entries(values).forEach(([qId, ans]) => {
      setClarificationAnswer(qId, String(ans))
    })
    const formatted = formatAnswersForSubmission()
    onSubmit(formatted)
  }

  return (
    <div className="border-t border-border px-3 py-3 space-y-3 bg-muted/30">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
        Clarification needed
      </p>
      <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-3">
        {clarificationBlock.questions.map((q: ClarificationQuestion) => (
          <QuestionWidget key={q.id} q={q} register={register} />
        ))}
        <button
          type="submit"
          className="w-full rounded-md bg-primary text-primary-foreground py-1.5 text-xs font-medium hover:opacity-90"
        >
          Submit answers
        </button>
      </form>
    </div>
  )
}

function QuestionWidget({
  q,
  register,
}: {
  q: ClarificationQuestion
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  register: any
}) {
  return (
    <div>
      <label className="text-xs font-medium block mb-1">
        {q.question}
        {q.required && <span className="text-destructive ml-0.5">*</span>}
      </label>

      {q.input_type === 'text' && (
        <textarea
          {...register(q.id)}
          placeholder={q.hint}
          rows={2}
          className="w-full rounded border border-input px-2 py-1 text-xs resize-none"
        />
      )}

      {q.input_type === 'select' && (
        <select
          {...register(q.id)}
          className="w-full rounded border border-input px-2 py-1 text-xs"
        >
          <option value="">Select…</option>
          {q.options.map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      )}

      {q.input_type === 'multiselect' && (
        <div className="space-y-1">
          {q.options.map((opt) => (
            <label key={opt} className="flex items-center gap-2 text-xs cursor-pointer">
              <input type="checkbox" value={opt} {...register(`${q.id}_${opt}`)} />
              {opt}
            </label>
          ))}
        </div>
      )}

      {q.input_type === 'boolean' && (
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" {...register(q.id)} className="rounded" />
          <span className="text-xs">{q.hint ?? 'Yes'}</span>
        </label>
      )}

      {q.input_type === 'number' && (
        <input
          type="number"
          {...register(q.id, { valueAsNumber: true })}
          placeholder={q.hint}
          className="w-full rounded border border-input px-2 py-1 text-xs"
        />
      )}
    </div>
  )
}
