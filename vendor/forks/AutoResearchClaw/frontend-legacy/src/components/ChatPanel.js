/**
 * ChatPanel — conversational research interface.
 */
const ChatPanel = {
  _messages: [],

  render(container) {
    container.innerHTML = `
      <div class="chat-container">
        <div class="chat-messages" id="chat-messages">
          <div class="chat-msg assistant">
            <div class="bubble">
              Welcome to ResearchClaw! I can help you with research topics,
              running experiments, monitoring progress, and editing papers.
              Just type your question below.
            </div>
          </div>
        </div>
        <div class="chat-input-area">
          <button class="voice-btn" id="voice-btn" title="Voice input">🎤</button>
          <input type="text" id="chat-input" placeholder="Ask about your research..." autocomplete="off" />
          <button id="chat-send">Send</button>
        </div>
      </div>
    `;

    const input = document.getElementById('chat-input');
    const send = document.getElementById('chat-send');
    const voiceBtn = document.getElementById('voice-btn');

    send.addEventListener('click', () => this._sendMessage());
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this._sendMessage();
      }
    });

    if (voiceBtn) {
      voiceBtn.addEventListener('click', () => this._toggleVoice(voiceBtn));
    }

    // Listen for chat responses
    chatWS.on('chat_response', (data) => {
      this._addMessage('assistant', data.message);
    });
    chatWS.on('error', (data) => {
      this._addMessage('assistant', `Error: ${data.error}`);
    });

    // Connect chat WebSocket
    chatWS.connect();
  },

  _sendMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;

    this._addMessage('user', text);
    chatWS.send(JSON.stringify({ message: text }));
    input.value = '';
    input.focus();
  },

  _addMessage(role, content) {
    const container = document.getElementById('chat-messages');
    if (!container) return;

    const div = document.createElement('div');
    div.className = `chat-msg ${role}`;

    // Simple markdown rendering
    const rendered = content
      .replace(/```([\s\S]*?)```/g, '<pre style="background:var(--bg-primary);padding:8px;border-radius:4px;font-size:12px;overflow-x:auto"><code>$1</code></pre>')
      .replace(/`([^`]+)`/g, '<code style="background:var(--bg-tertiary);padding:2px 4px;border-radius:3px;font-size:13px">$1</code>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>')
      .replace(/^- (.+)/gm, '<li>$1</li>');

    div.innerHTML = `<div class="bubble">${rendered}</div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;

    this._messages.push({ role, content });
  },

  _toggleVoice(btn) {
    // Voice recording toggle (simplified)
    if (btn.classList.contains('recording')) {
      btn.classList.remove('recording');
      btn.textContent = '🎤';
    } else {
      btn.classList.add('recording');
      btn.textContent = '⏹';
      // In production, use MediaRecorder API here
    }
  },

  onEvent() {}
};
