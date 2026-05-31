import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import { chatApi } from "@/lib/api";
import { useChat } from "@/hooks/useChat";
import { Plus, Send, Trash2 } from "lucide-react";

const AGENT_COLORS: Record<string, string> = {
  qa: "bg-blue-100 text-blue-700",
  portfolio: "bg-green-100 text-green-700",
  market: "bg-purple-100 text-purple-700",
  goals: "bg-orange-100 text-orange-700",
  news: "bg-pink-100 text-pink-700",
  tax: "bg-yellow-100 text-yellow-700",
};

const SUGGESTIONS = [
  "What is dollar-cost averaging?",
  "Explain the difference between a Roth IRA and Traditional IRA",
  "What's the S&P 500 trading at today?",
  "How do I analyze my portfolio's diversification?",
  "Help me plan for retirement in 20 years",
];

export default function ChatPage() {
  const { conversationId } = useParams<{ conversationId?: string }>();
  const [activeConvId, setActiveConvId] = useState<string | null>(conversationId || null);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { messages, streaming, connected, send, loadHistory } = useChat(activeConvId);

  // Refresh sidebar title as soon as streaming completes (first message sets the title)
  const prevStreamingRef = useRef<typeof streaming>(null);
  useEffect(() => {
    if (prevStreamingRef.current !== null && streaming === null) {
      qc.invalidateQueries({ queryKey: ["conversations"] });
    }
    prevStreamingRef.current = streaming;
  }, [streaming, qc]);

  const { data: conversations } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => chatApi.listConversations().then((r) => r.data),
  });

  const { data: history } = useQuery({
    queryKey: ["messages", activeConvId],
    queryFn: () => chatApi.getMessages(activeConvId!).then((r) => r.data),
    enabled: !!activeConvId,
  });

  useEffect(() => {
    if (history) loadHistory(history);
  }, [history]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming?.content]);

  const deleteConversation = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm("Delete this conversation?")) return;
    await chatApi.deleteConversation(id);
    qc.invalidateQueries({ queryKey: ["conversations"] });
    if (activeConvId === id) {
      setActiveConvId(null);
      navigate("/");
    }
  };

  const newConversation = async () => {
    const res = await chatApi.createConversation();
    const conv = res.data;
    qc.invalidateQueries({ queryKey: ["conversations"] });
    setActiveConvId(conv.id);
    navigate(`/chat/${conv.id}`);
  };

  const handleSend = () => {
    if (!input.trim() || !activeConvId) return;
    send(input.trim());
    setInput("");
  };

  return (
    <div className="flex h-full">
      {/* Conversations sidebar */}
      <div className="w-60 bg-gray-50 border-r flex flex-col shrink-0 hidden md:flex">
        <div className="p-3 border-b">
          <button
            onClick={newConversation}
            className="flex items-center gap-2 w-full bg-amber-500 hover:bg-amber-600 text-white px-3 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            <Plus size={16} /> New Chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto py-2">
          {(conversations || []).map((c: any) => (
            <div
              key={c.id}
              className={`group flex items-center gap-1 px-3 py-2 text-sm hover:bg-gray-100 transition-colors cursor-pointer ${
                c.id === activeConvId ? "bg-amber-50 font-medium text-amber-700" : "text-gray-700"
              }`}
              onClick={() => { setActiveConvId(c.id); navigate(`/chat/${c.id}`); }}
            >
              <span className="flex-1 truncate">{c.title}</span>
              <button
                onClick={(e) => deleteConversation(e, c.id)}
                className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-opacity shrink-0"
                title="Delete"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {!activeConvId && (
            <div className="flex flex-col items-center justify-center h-full text-center px-4">
              <span className="text-6xl mb-4">⚜️</span>
              <h2 className="text-2xl font-bold text-gray-800 mb-2">Welcome to Aurum</h2>
              <p className="text-gray-500 mb-8 max-w-md">
                Your AI-powered financial education assistant. Ask me anything about investing,
                your portfolio, market trends, or financial goals.
              </p>
              <button
                onClick={newConversation}
                className="bg-amber-500 hover:bg-amber-600 text-white px-6 py-3 rounded-xl font-semibold transition-colors mb-6"
              >
                Start a Conversation
              </button>
              <div className="grid grid-cols-1 gap-2 w-full max-w-lg">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={async () => {
                      const res = await chatApi.createConversation(s.slice(0, 60));
                      const conv = res.data;
                      qc.invalidateQueries({ queryKey: ["conversations"] });
                      setActiveConvId(conv.id);
                      navigate(`/chat/${conv.id}`);
                      setTimeout(() => send(s), 500);
                    }}
                    className="text-left px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm text-gray-700 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                msg.role === "user"
                  ? "bg-amber-500 text-white"
                  : "bg-white border shadow-sm"
              }`}>
                {msg.role === "assistant" && msg.agents_used?.length ? (
                  <div className="flex flex-wrap gap-1 mb-2">
                    {msg.agents_used.map((a) => (
                      <span key={a} className={`text-xs px-2 py-0.5 rounded-full font-medium ${AGENT_COLORS[a] || "bg-gray-100 text-gray-600"}`}>
                        {a}
                      </span>
                    ))}
                  </div>
                ) : null}
                <div className={msg.role === "assistant" ? "prose-chat" : "text-sm"}>
                  {msg.role === "assistant" ? (
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  ) : (
                    msg.content
                  )}
                </div>
                {msg.citations?.length ? (
                  <div className="mt-2 pt-2 border-t border-gray-200 space-y-1">
                    {msg.citations.map((c, i) => (
                      <div key={i} className="text-xs text-gray-500">
                        {c.source_url ? (
                          <a href={c.source_url} target="_blank" rel="noreferrer" className="text-amber-600 hover:underline">
                            📚 {c.source_title}
                          </a>
                        ) : (
                          <span>📚 {c.source_title}</span>
                        )}
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          ))}

          {streaming && (
            <div className="flex justify-start">
              <div className="max-w-[80%] bg-white border shadow-sm rounded-2xl px-4 py-3">
                {streaming.agentsUsed.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-2">
                    {streaming.agentsUsed.map((a) => (
                      <span key={a} className={`text-xs px-2 py-0.5 rounded-full font-medium ${AGENT_COLORS[a] || "bg-gray-100"}`}>
                        {a}
                        {a === streaming.currentAgent && " ●"}
                      </span>
                    ))}
                  </div>
                )}
                <div className="prose-chat">
                  <ReactMarkdown>{streaming.content || "..."}</ReactMarkdown>
                </div>
                <span className="cursor-blink text-amber-500">▌</span>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t bg-white">
          <div className="flex gap-2 max-w-4xl mx-auto">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder={activeConvId ? "Ask about investing, your portfolio, market data..." : "Start a conversation first"}
              disabled={!activeConvId || !!streaming}
              rows={1}
              className="flex-1 border rounded-xl px-4 py-2.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-amber-500 disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={!activeConvId || !input.trim() || !!streaming}
              className="bg-amber-500 hover:bg-amber-600 text-white px-4 py-2.5 rounded-xl transition-colors disabled:opacity-50"
            >
              <Send size={18} />
            </button>
          </div>
          {!connected && activeConvId && (
            <p className="text-center text-xs text-gray-400 mt-1">Connecting...</p>
          )}
        </div>
      </div>
    </div>
  );
}
