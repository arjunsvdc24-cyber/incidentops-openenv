import type { WsMessage } from './types';

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let currentOnMessage: ((msg: WsMessage) => void) | null = null;

export function createWebSocket(onMessage: (msg: WsMessage) => void): WebSocket {
  currentOnMessage = onMessage;
  const wsUrl = `${window.location.origin.replace('http', 'ws')}/ws`;

  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WsMessage;
        onMessage(message);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected, reconnecting in 3s...');
      if (reconnectTimer) clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(() => {
        if (currentOnMessage) {
          ws = createWebSocket(currentOnMessage);
        }
      }, 3000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return ws;
  } catch (e) {
    console.error('Failed to create WebSocket:', e);
    throw e;
  }
}

export function closeWebSocket(): void {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (ws) {
    ws.close();
    ws = null;
  }
  currentOnMessage = null;
}

export function sendWsMessage(message: unknown): void {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message));
  }
}
