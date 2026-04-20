// WebSocket client for real-time updates

export type WSEventType =
  | 'run.started'
  | 'run.step.started'
  | 'run.step.completed'
  | 'run.completed'
  | 'run.failed'
  | 'run.log'
  | 'run.metric'
  | 'experiment.trial.started'
  | 'experiment.trial.completed'
  | 'experiment.completed'
  | 'dashboard.metrics'
  | 'dashboard.activity'
  | 'dashboard.alert'
  | 'system.health'

export interface WSMessage {
  type: WSEventType
  data: Record<string, unknown>
  timestamp: string
}

type MessageHandler = (message: WSMessage) => void

class WebSocketClient {
  private ws: WebSocket | null = null
  private handlers: Map<string, Set<MessageHandler>> = new Map()
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private url: string = ''

  connect(baseUrl?: string) {
    const wsUrl = baseUrl || this.getWebSocketUrl()
    this.url = wsUrl

    try {
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        console.log('[WS] Connected to', wsUrl)
        this.reconnectAttempts = 0
      }

      this.ws.onmessage = (event) => {
        try {
          const message: WSMessage = JSON.parse(event.data)
          this.dispatch(message)
        } catch (err) {
          console.error('[WS] Failed to parse message:', err)
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

  subscribeRun(runId: string, handler: MessageHandler): () => void {
    return this.subscribe(`run:${runId}`, handler)
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
