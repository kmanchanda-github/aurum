import { useCallback, useRef, useState } from "react";
import { getToken } from "@/lib/auth";
import { streamChat, type SSEConnection } from "@/lib/ws";

export interface Citation {
  source_title: string;
  source_url?: string;
  snippet?: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  agents_used?: string[];
  citations?: Citation[];
  created_at?: string;
}

export interface StreamState {
  content: string;
  currentAgent: string | null;
  agentsUsed: string[];
  citations: Citation[];
}

export function useChat(conversationId: string | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState<StreamState | null>(null);
  const [connected] = useState(true); // SSE connects per-request — always "ready"
  const activeStream = useRef<SSEConnection | null>(null);

  const send = useCallback(
    (content: string) => {
      if (!conversationId) return;
      const token = getToken();
      if (!token) return;

      // Cancel any in-flight stream
      activeStream.current?.cancel();

      // Optimistically add user message
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "user", content },
      ]);
      setStreaming({ content: "", currentAgent: null, agentsUsed: [], citations: [] });

      activeStream.current = streamChat(
        conversationId,
        token,
        content,
        // onFrame
        (frame) => {
          switch (frame.type) {
            case "agent_start":
              setStreaming((s) => ({
                content: s?.content ?? "",
                currentAgent: frame.agent as string,
                agentsUsed: [...(s?.agentsUsed ?? []), frame.agent as string],
                citations: s?.citations ?? [],
              }));
              break;

            case "token":
              setStreaming((s) => ({
                content: (s?.content ?? "") + (frame.delta as string),
                currentAgent: s?.currentAgent ?? null,
                agentsUsed: s?.agentsUsed ?? [],
                citations: s?.citations ?? [],
              }));
              break;

            case "citation":
              setStreaming((s) => ({
                content: s?.content ?? "",
                currentAgent: s?.currentAgent ?? null,
                agentsUsed: s?.agentsUsed ?? [],
                citations: [
                  ...(s?.citations ?? []),
                  {
                    source_title: frame.source_title as string,
                    source_url: frame.source_url as string | undefined,
                    snippet: frame.snippet as string | undefined,
                  },
                ],
              }));
              break;

            case "final":
              setMessages((prev) => [
                ...prev,
                {
                  id: frame.message_id as string,
                  role: "assistant",
                  content: frame.content as string,
                  agents_used: frame.agents_used as string[],
                  citations: frame.citations as Citation[],
                },
              ]);
              setStreaming(null);
              break;

            case "error":
              setStreaming(null);
              break;
          }
        },
        // onDone
        () => {
          setStreaming(null);
          activeStream.current = null;
        },
        // onError
        (_err) => {
          setStreaming(null);
          activeStream.current = null;
        },
      );
    },
    [conversationId],
  );

  const loadHistory = useCallback((history: Message[]) => {
    setMessages(history);
  }, []);

  return { messages, streaming, connected, send, loadHistory };
}
