/**
 * Chat streaming via SSE (Server-Sent Events).
 *
 * Replaces the WebSocket transport which is blocked by HF Spaces and many
 * corporate proxies. SSE uses plain HTTP POST + streaming response so it
 * works everywhere HTTP/1.1 works.
 */

const API_BASE = import.meta.env.VITE_API_BASE || "";

export interface SSEFrame {
  type: "agent_start" | "agent_end" | "token" | "citation" | "final" | "error";
  [key: string]: unknown;
}

export interface SSEConnection {
  cancel: () => void;
}

/**
 * POST a message and stream the SSE response.
 * Calls `onFrame` for each parsed event, `onDone` when the stream ends.
 */
export function streamChat(
  conversationId: string,
  token: string,
  content: string,
  onFrame: (frame: SSEFrame) => void,
  onDone: () => void,
  onError: (err: string) => void,
): SSEConnection {
  const controller = new AbortController();

  (async () => {
    try {
      const resp = await fetch(
        `${API_BASE}/api/chat/stream?conversation_id=${encodeURIComponent(conversationId)}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ content }),
          signal: controller.signal,
        },
      );

      if (!resp.ok) {
        onError(`HTTP ${resp.status}`);
        return;
      }

      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE messages are separated by "\n\n"
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          for (const line of part.split("\n")) {
            if (line.startsWith("data: ")) {
              try {
                const frame: SSEFrame = JSON.parse(line.slice(6));
                onFrame(frame);
              } catch {
                // malformed JSON — skip
              }
            }
          }
        }
      }

      onDone();
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return;
      onError(err instanceof Error ? err.message : String(err));
    }
  })();

  return { cancel: () => controller.abort() };
}
