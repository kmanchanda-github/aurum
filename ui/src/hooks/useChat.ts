import { useCallback, useEffect, useRef, useState } from "react";
import { getToken } from "@/lib/auth";
import { createChatWS } from "@/lib/ws";

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

const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;
const RECONNECT_MAX_ATTEMPTS = 8;

export function useChat(conversationId: string | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState<StreamState | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Track whether the hook is still mounted to avoid state updates after unmount
  const mountedRef = useRef(true);

  const clearReconnectTimer = () => {
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  };

  const connect = useCallback(() => {
    if (!conversationId) return;
    const token = getToken();
    if (!token) return;

    const ws = createChatWS(conversationId, token);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      reconnectAttemptsRef.current = 0;
      setConnected(true);
    };

    ws.onclose = (ev) => {
      if (!mountedRef.current) return;
      setConnected(false);
      // Don't reconnect if the close was clean (code 1000) or we're at max attempts
      if (
        ev.code !== 1000 &&
        reconnectAttemptsRef.current < RECONNECT_MAX_ATTEMPTS
      ) {
        const delay = Math.min(
          RECONNECT_BASE_MS * 2 ** reconnectAttemptsRef.current,
          RECONNECT_MAX_MS
        );
        reconnectAttemptsRef.current += 1;
        reconnectTimerRef.current = setTimeout(connect, delay);
      }
    };

    ws.onmessage = (ev) => {
      if (!mountedRef.current) return;
      const frame = JSON.parse(ev.data);

      switch (frame.type) {
        case "agent_start":
          setStreaming((s) => ({
            content: s?.content ?? "",
            currentAgent: frame.agent,
            agentsUsed: [...(s?.agentsUsed ?? []), frame.agent],
            citations: s?.citations ?? [],
          }));
          break;

        case "token":
          setStreaming((s) => ({
            content: (s?.content ?? "") + frame.delta,
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
                source_title: frame.source_title,
                source_url: frame.source_url,
                snippet: frame.snippet,
              },
            ],
          }));
          break;

        case "final":
          setMessages((prev) => [
            ...prev,
            {
              id: frame.message_id,
              role: "assistant",
              content: frame.content,
              agents_used: frame.agents_used,
              citations: frame.citations,
            },
          ]);
          setStreaming(null);
          break;

        case "error":
          setStreaming(null);
          break;
      }
    };
  }, [conversationId]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      clearReconnectTimer();
      wsRef.current?.close(1000, "component unmounted");
      wsRef.current = null;
    };
  }, [connect]);

  const send = useCallback(
    (content: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "user", content },
      ]);
      wsRef.current.send(JSON.stringify({ content }));
      setStreaming({ content: "", currentAgent: null, agentsUsed: [], citations: [] });
    },
    []
  );

  const loadHistory = useCallback((history: Message[]) => {
    setMessages(history);
  }, []);

  return { messages, streaming, connected, send, loadHistory };
}
