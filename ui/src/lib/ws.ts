const WS_BASE = import.meta.env.VITE_WS_BASE || `ws://${window.location.host}`;

export function createChatWS(conversationId: string, token: string): WebSocket {
  const url = `${WS_BASE}/api/chat/ws?conversation_id=${conversationId}&token=${token}`;
  return new WebSocket(url);
}
