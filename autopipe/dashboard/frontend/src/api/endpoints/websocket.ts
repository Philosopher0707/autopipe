// WebSocket client for real-time updates

import { useAuthStore } from '@/stores/authStore'

/**
 * Canonical WS contract (docs/architecture/WS_CONTRACT.md): every message is
 * `{type, data, timestamp}` with all payload fields inside `data`. These are
 * exactly the event types the backend emits — no aspirational entries.
 */
export type WSEventType =
  | 'run.status'
  | 'run.log'
  | 'run.metric'
  | 'drift.alert'
  | 'model.promoted'
  | `dashboard.${string}`

export interface WSMessage {
  type: WSEventType
  data: Record<string, unknown>
  timestamp: string
}

/** Parse an incoming frame; returns null for malformed/foreign payloads. */
export function parseWSMessage(raw: string): WSMessage | null {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return null
  }
  if (!parsed || typeof parsed !== 'object') return null
  const msg = parsed as Record<string, unknown>
  if (typeof msg.type !== 'string' || msg.type === '') return null
  const data =
    msg.data && typeof msg.data === 'object' && !Array.isArray(msg.data)
      ? (msg.data as Record<string, unknown>)
      : {}
  return {
    type: msg.type as WSEventType,
    data,
    timestamp: typeof msg.timestamp === 'string' ? msg.timestamp : '',
  }
}

type MessageHandler = (message: WSMessage) => void

export class WebSocketClient {
  private ws: WebSocket | null = null
  private handlers: Map<string, Set<MessageHandler>> = new Map()
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private url: string = ''

  connect(baseUrl?: string) {
    // Store the bare URL so reconnects re-read the token from the store
    // instead of replaying a possibly-expired one.
    const bareUrl = baseUrl || this.getWebSocketUrl()
    this.url = bareUrl
    const wsUrl = this.withToken(bareUrl)

    try {
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        console.log('[WS] Connected to', wsUrl)
        this.reconnectAttempts = 0
      }

      this.ws.onmessage = (event) => {
        const message = parseWSMessage(event.data)
        if (message) {
          this.dispatch(message)
        } else {
          console.warn('[WS] Ignoring malformed message')
        }
      }

      this.ws.onclose = () => {
        console.log('[WS] Disconnected')
        this.attemptReconnect()
      }

      this.ws.onerror = (error) => {
        console.error('[WS] Error:', error)
      }
    } catch (err) {
      console.error('[WS] Connection failed:', err)
      this.attemptReconnect()
    }
  }

  private getWebSocketUrl(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = import.meta.env.VITE_WS_URL || `${protocol}//${window.location.host}`
    return `${host}/api/v1/ws/dashboard`
  }

  /**
   * The backend rejects unauthenticated WS handshakes (close 1008), and
   * browsers cannot set an Authorization header on WebSocket, so the access
   * token travels as a query parameter. Attaching it here — in connect() —
   * means every caller (including pages that pass an explicit run-scoped
   * URL) is authenticated; RunDetail used to build its URL without a token
   * and was silently disconnected by the server.
   */
  private withToken(url: string): string {
    return WebSocketClient.tokenUrl(url, useAuthStore.getState().token)
  }

  /** The token-attachment rule for a WS URL (exported for tests). */
  static tokenUrl(url: string, token: string | null): string {
    if (url.includes('token=') || !token) return url
    return `${url}${url.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`
  }

  private attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
      console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)
      setTimeout(() => this.connect(this.url), delay)
    }
  }

  disconnect() {
    this.reconnectAttempts = this.maxReconnectAttempts // prevent reconnect
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  subscribe(eventType: string, handler: MessageHandler): () => void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set())
    }
    this.handlers.get(eventType)!.add(handler)

    // Return unsubscribe function
    return () => {
      this.handlers.get(eventType)?.delete(handler)
    }
  }

  subscribeExperiment(experimentId: string, handler: MessageHandler): () => void {
    return this.subscribe(`experiment:${experimentId}`, handler)
  }

  private dispatch(message: WSMessage) {
    const handlers = this.handlers.get(message.type)
    if (handlers) {
      handlers.forEach((handler) => handler(message))
    }
    // Also dispatch to wildcard handlers
    const allHandlers = this.handlers.get('*')
    if (allHandlers) {
      allHandlers.forEach((handler) => handler(message))
    }
  }

  send(message: Record<string, unknown>) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    }
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }
}

// Singleton instance
export const wsClient = new WebSocketClient()
