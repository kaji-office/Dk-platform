'use client'

import { useEffect, useRef } from 'react'
import { useChatStore } from '@/stores/chatStore'

export function MessageThread() {
  const messages = useChatStore((s) => s.messages)
  const isStreaming = useChatStore((s) => s.isStreaming)
  const streamingContent = useChatStore((s) => s.streamingContent)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  const STARTER_PROMPTS = [
    'Build a workflow that summarises emails and sends a Slack message',
    'Create a scheduled report that queries an API and emails results',
    'Make a webhook that processes incoming data and stores it',
    'Design a multi-step AI agent that researches and summarises topics',
  ]

  return (
    <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
      {/* Empty state — prompt suggestions */}
      {messages.length === 0 && !isStreaming && (
        <div className="space-y-2 py-4">
          <p className="text-xs text-muted-foreground text-center">
            Describe the workflow you want to build
          </p>
          <div className="grid grid-cols-1 gap-1.5">
            {STARTER_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                onClick={() =>
                  useChatStore.getState().appendMessage({
                    id: `suggest_${Date.now()}`,
                    role: 'user',
                    content: prompt,
                    ts: new Date().toISOString(),
                  })
                }
                className="text-left text-xs rounded-md border border-border px-2.5 py-2 hover:bg-muted transition-colors line-clamp-2"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Messages */}
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          <div
            className={`max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
              msg.role === 'user'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-foreground'
            }`}
          >
            <p className="whitespace-pre-wrap break-words">{msg.content}</p>
          </div>
        </div>
      ))}

      {/* Streaming indicator */}
      {isStreaming && (
        <div className="flex justify-start">
          <div className="bg-muted rounded-lg px-3 py-2 text-sm">
            <span className="inline-flex gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:0ms]" />
              <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:150ms]" />
              <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:300ms]" />
            </span>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
