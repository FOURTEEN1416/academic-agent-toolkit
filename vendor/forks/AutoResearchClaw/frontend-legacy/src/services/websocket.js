/**
 * WebSocket client for ResearchClaw events and chat.
 */
class RCWebSocket {
  constructor(path, options = {}) {
    this.path = path;
    this.reconnectInterval = options.reconnectInterval || 3000;
    this.maxReconnects = options.maxReconnects || 10;
    this.listeners = {};
    this.ws = null;
    this._reconnects = 0;
    this._closed = false;
  }

  connect() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${location.host}${this.path}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this._reconnects = 0;
      this._emit('open', {});
    };

    this.ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        this._emit(data.type, data.data, data.timestamp);
        this._emit('message', data);
      } catch (e) {
        console.warn('Failed to parse WS message:', e);
      }
    };

    this.ws.onclose = () => {
      this._emit('close', {});
      if (!this._closed && this._reconnects < this.maxReconnects) {
        this._reconnects++;
        setTimeout(() => this.connect(), this.reconnectInterval);
      }
    };

    this.ws.onerror = (err) => {
      this._emit('error', { error: err });
    };
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(typeof data === 'string' ? data : JSON.stringify(data));
    }
  }

  on(event, callback) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(callback);
    return this;
  }

  off(event, callback) {
    if (this.listeners[event]) {
      this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
    }
  }

  close() {
    this._closed = true;
    if (this.ws) this.ws.close();
  }

  _emit(event, data, timestamp) {
    (this.listeners[event] || []).forEach(cb => cb(data, timestamp));
  }
}

// Singleton instances
const eventsWS = new RCWebSocket('/ws/events');
const chatWS = new RCWebSocket('/ws/chat');
