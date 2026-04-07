import React, { useEffect, useState, useRef } from 'react';
import { Send, User, Bot, Loader2, Plus, MessageSquare, Search, MoreHorizontal } from 'lucide-react';
import useChatStore from '../store/useChatStore';
import { toast } from 'react-toastify';

const Chat = () => {
  const { sessions, activeSession, messages, loading, error, fetchSessions, createSession, setActiveSession, sendMessage } = useChatStore();
  const [content, setContent] = useState('');
  const messagesEndRef = useRef(null);

  useEffect(() => {
    fetchSessions();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!content.trim() || !activeSession) return;
    const msg = content;
    setContent('');
    await sendMessage(activeSession.id, msg);
  };

  const handleNewSession = async () => {
    const session = await createSession();
    if (!session) {
      toast.error(error || 'Failed to start a new chat.');
    }
  };

  return (
    <div className="h-[calc(100vh-8rem)] flex gap-6 animate-fade-in overflow-hidden">
      {/* Sessions Sidebar */}
      <div className="w-80 flex flex-col bg-white border border-neutral-100 rounded-2xl overflow-hidden shadow-sm">
        <div className="p-4 border-b border-neutral-50 flex items-center justify-between">
           <h2 className="text-xl font-bold text-neutral-900">Chats</h2>
           <button 
             onClick={handleNewSession}
             className="p-2 text-primary-600 hover:bg-primary-50 rounded-lg transition-colors border border-primary-100"
             title="New Chat"
           >
             <Plus size={20} />
           </button>
        </div>
        
        <div className="p-4 bg-neutral-50 border-b border-neutral-100">
           <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400">
                <Search size={16} />
              </span>
              <input 
                type="text" 
                placeholder="Search conversations..." 
                className="w-full pl-9 pr-4 py-2 bg-white border border-neutral-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/20"
              />
           </div>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {sessions.map((session) => (
            <button
              key={session.id}
              onClick={() => setActiveSession(session)}
              className={`w-full flex items-center gap-3 p-3 rounded-xl transition-all duration-200 group relative ${
                activeSession?.id === session.id 
                  ? 'bg-primary-50 text-primary-700 font-medium' 
                  : 'text-neutral-500 hover:bg-neutral-50 hover:text-neutral-700'
              }`}
            >
              <div className={`p-2 rounded-lg ${activeSession?.id === session.id ? 'bg-primary-100' : 'bg-neutral-100 group-hover:bg-neutral-200'}`}>
                <MessageSquare size={16} />
              </div>
              <span className="truncate flex-1 text-left text-sm">{session.title || 'Untitled Chat'}</span>
              <button className="opacity-0 group-hover:opacity-100 p-1 text-neutral-400 hover:text-neutral-600">
                <MoreHorizontal size={16} />
              </button>
            </button>
          ))}
          {sessions.length === 0 && (
            <div className="text-center py-12 px-6">
              <div className="bg-neutral-50 p-4 rounded-full w-fit mx-auto mb-3">
                <MessageSquare size={24} className="text-neutral-300" />
              </div>
              <p className="text-sm text-neutral-400 italic">No conversations yet.</p>
              <button onClick={handleNewSession} className="text-sm text-primary-600 font-medium mt-2 hover:underline">Start a new one</button>
            </div>
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col bg-white border border-neutral-100 rounded-2xl overflow-hidden shadow-sm">
        {activeSession ? (
          <>
            {/* Header */}
            <div className="px-6 py-4 border-b border-neutral-50 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="bg-primary-100 p-2 rounded-lg text-primary-600">
                   <Bot size={20} />
                </div>
                <div>
                   <p className="font-bold text-neutral-900">{activeSession.title || 'Workflow Assistant'}</p>
                   <p className="text-xs text-green-500 font-medium flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
                      AI Agent Online
                   </p>
                </div>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {messages.map((msg, idx) => (
                <div 
                  key={idx}
                  className={`flex items-start gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''} animate-fade-in`}
                >
                  <div className={`p-2 rounded-xl flex-shrink-0 ${msg.role === 'user' ? 'bg-primary-600 text-white' : 'bg-neutral-100 text-neutral-600'}`}>
                    {msg.role === 'user' ? <User size={20} /> : <Bot size={20} />}
                  </div>
                  <div className={`max-w-[70%] p-4 rounded-2xl text-sm leading-relaxed ${
                    msg.role === 'user' 
                      ? 'bg-primary-600 text-white rounded-tr-none' 
                      : 'bg-neutral-100 text-neutral-900 rounded-tl-none border border-neutral-200/50'
                  }`}>
                    {msg.content}
                    <p className={`text-[10px] mt-2 font-medium opacity-60 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
                       {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex items-start gap-4 animate-pulse">
                   <div className="p-2 rounded-xl bg-neutral-100 text-neutral-400">
                     <Bot size={20} />
                   </div>
                   <div className="p-4 bg-neutral-100 rounded-2xl rounded-tl-none w-24">
                     <div className="flex gap-1.5">
                       <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 animate-bounce"></span>
                       <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 animate-bounce [animation-delay:-0.15s]"></span>
                       <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 animate-bounce [animation-delay:-0.3s]"></span>
                     </div>
                   </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-6 border-t border-neutral-50 bg-white">
              <form onSubmit={handleSend} className="relative">
                <input 
                   disabled={loading}
                   className="w-full input-field py-4 pl-6 pr-14 text-sm resize-none h-14"
                   placeholder="Ask anything about your workflows..."
                   value={content}
                   onChange={(e) => setContent(e.target.value)}
                />
                <button 
                  type="submit"
                  disabled={!content.trim() || loading}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-primary-600 text-white rounded-xl hover:bg-primary-700 transition-all disabled:opacity-30 disabled:hover:bg-primary-600"
                >
                  <Send size={18} />
                </button>
              </form>
              <p className="text-[10px] text-neutral-400 text-center mt-3 font-medium">
                 Powered by DK-AI Assistant • High performance workflow automation
              </p>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-12 text-center">
             <div className="p-6 bg-primary-50 rounded-full text-primary-600 mb-6 border border-primary-100 shadow-inner group">
                <MessageSquare size={48} className="group-hover:scale-110 transition-transform" />
             </div>
             <h2 className="text-2xl font-bold text-neutral-900 mb-2">AI Assistant</h2>
             <p className="text-neutral-500 max-w-sm mb-8">
               Select a conversation or start a new one to begin interacting with our powerful AI.
             </p>
             <button 
                onClick={handleNewSession}
                className="btn-primary"
              >
               Start New Chat
             </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default Chat;
