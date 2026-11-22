export type EventType =
  | "INVOICE_PROCESSED"
  | "INVOICE_UPLOADED"
  | "PRICE_ALERT"
  | "STOCK_UPDATE"
  | "DEMAND_LOGGED"
  | "DEMAND_UPDATED"
  | "PROFIT_LEAK"
  | "DATA_RESET"
  | "SYSTEM_STATUS";

export interface RealtimeEvent {
  event_id: string;
  type: EventType;
  business_id: string;
  title: string;
  message: string;
  data: Record<string, any>;
  timestamp: string;
}

export type ConnectionStatus = "connected" | "connecting" | "disconnected";

export type EventListener = (event: RealtimeEvent) => void;

export class RealtimeClient {
  private ws: WebSocket | null = null;
  private businessId: string;
  private listeners: Set<EventListener> = new Set();
  private statusListeners: Set<(status: ConnectionStatus) => void> = new Set();
  private reconnectTimer: any = null;
  private pingTimer: any = null;
  private reconnectAttempts = 0;
  private isDestroyed = false;

  constructor(businessId: string) {
    this.businessId = businessId;
    this.connect();
  }

  private getWebSocketUrl(): string {
    const isBrowser = typeof window !== "undefined";
    if (!isBrowser) return "";
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    // In dev, FastAPI runs on port 8000
    const host = window.location.hostname === "localhost" ? "127.0.0.1:8000" : window.location.host;
    return `${protocol}//${host}/api/v1/ws/${this.businessId}`;
  }

  public connect(): void {
    if (typeof window === "undefined" || this.isDestroyed) return;
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.notifyStatus("connecting");
    const url = this.getWebSocketUrl();

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.notifyStatus("connected");
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        if (event.data === "pong") return;
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === "pong") return;
          this.listeners.forEach((listener) => {
            try {
              listener(payload);
            } catch (err) {
              console.error("[Realtime] Listener error:", err);
            }
          });
        } catch (e) {
          // Non-JSON message
        }
      };

      this.ws.onclose = () => {
        this.stopHeartbeat();
        this.notifyStatus("disconnected");
        this.scheduleReconnect();
      };

      this.ws.onerror = () => {
        this.ws?.close();
      };
    } catch (e) {
      this.notifyStatus("disconnected");
      this.scheduleReconnect();
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.pingTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send("ping");
      }
    }, 20000);
  }

  private stopHeartbeat(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.isDestroyed || this.reconnectTimer) return;
    const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), 10000);
    this.reconnectAttempts++;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  public subscribe(listener: EventListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  public onStatusChange(callback: (status: ConnectionStatus) => void): () => void {
    this.statusListeners.add(callback);
    return () => this.statusListeners.delete(callback);
  }

  private notifyStatus(status: ConnectionStatus): void {
    this.statusListeners.forEach((cb) => cb(status));
  }

  public disconnect(): void {
    this.isDestroyed = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
