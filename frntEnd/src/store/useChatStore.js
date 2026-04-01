import { create } from 'zustand';
import api from '../services/api';

const unwrapPayload = (data) => data?.data ?? data;

const normalizeSession = (session) => ({
  ...session,
  id: session?.id ?? session?.session_id,
});

const normalizeMessage = (message) => ({
  ...message,
  id: message?.id ?? `${message?.role || 'msg'}-${message?.ts || Date.now()}`,
  created_at: message?.created_at ?? message?.ts ?? new Date().toISOString(),
});

const useChatStore = create((set, get) => ({
  sessions: [],
  activeSession: null,
  messages: [],
  loading: false,
  error: null,

  fetchSessions: async () => {
    try {
      const response = await api.get('/chat/sessions');
      const payload = unwrapPayload(response.data);
      const sessions = Array.isArray(payload)
        ? payload
        : payload?.items || payload?.sessions || payload?.data || [];
      set({ sessions: sessions.map(normalizeSession) });
    } catch (err) {
      // Some backend builds expose create/send chat but not list sessions.
      if (err?.response?.status === 404) {
        set({ sessions: [] });
        return;
      }
      console.error('Failed to fetch sessions.');
    }
  },

  createSession: async (title = 'New Chat') => {
    try {
      const body = {
        initial_message: 'I want to build a workflow',
      };
      if (title) body.title = title;
      const response = await api.post('/chat/sessions', body);
      const payload = unwrapPayload(response.data);
      const sessionPayload = payload?.session || payload?.chat_session || payload;
      const session = normalizeSession(sessionPayload);
      if (!session?.id) {
        throw new Error('Session id missing in create-session response.');
      }
      set((state) => ({ 
        sessions: [session, ...state.sessions], 
        activeSession: session,
        messages: [],
        error: null,
      }));
      return session;
    } catch (err) {
      const message =
        err?.response?.data?.message ||
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        'Failed to create session';
      set({ error: message });
      console.error(message);
      return null;
    }
  },

  setActiveSession: (session) => {
    set({ activeSession: session, messages: [] });
    get().fetchMessages(session.id);
  },

  fetchMessages: async (sessionId) => {
    set({ loading: true });
    try {
      const response = await api.get(`/chat/sessions/${sessionId}`);
      const payload = unwrapPayload(response.data);
      const messages = payload?.messages || payload?.items || [];
      set({ messages: messages.map(normalizeMessage), loading: false });
    } catch (err) {
      set({ loading: false });
    }
  },

  sendMessage: async (sessionId, content) => {
    // Optimistic update
    const userMsg = { id: Date.now(), content, role: 'user', created_at: new Date().toISOString() };
    set((state) => ({ messages: [...state.messages, userMsg] }));

    try {
      const response = await api.post(`/chat/sessions/${sessionId}/messages`, { message: content });
      const payload = unwrapPayload(response.data);
      const assistantMsg = normalizeMessage({
        ...(payload || {}),
        role: payload?.role || 'assistant',
        content: payload?.content ?? payload?.reply ?? '',
      });
      set((state) => ({ 
        messages: [...state.messages.filter(m => m.id !== userMsg.id), userMsg, assistantMsg] 
      }));
    } catch (err) {
      console.error('Failed to send message');
    }
  }
}));


export default useChatStore;
