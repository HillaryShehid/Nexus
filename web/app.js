const messages = document.querySelector('#messages');
const form = document.querySelector('#chat-form');
const input = document.querySelector('#input');
const statusEl = document.querySelector('#status');
const dot = document.querySelector('.dot');
const mic = document.querySelector('#mic');
const voiceStatus = document.querySelector('#voice-status');
const speakToggle = document.querySelector('#speak-toggle');
let speakResponses = false;
let recognition = null;

function addMessage(who, text) {
  const el = document.createElement('div');
  el.className = 'message ' + (who === 'You' ? 'user' : 'nexus');
  const label = document.createElement('div');
  label.className = 'label';
  label.textContent = who === 'You' ? 'YOU' : 'NEXUS';
  el.append(label, document.createTextNode(text));
  messages.appendChild(el);
  messages.scrollTop = messages.scrollHeight;
  return el;
}

async function checkHealth() {
  try {
    const response = await fetch('/api/health', { credentials: 'same-origin' });
    if (!response.ok) throw new Error();
    const data = await response.json();
    statusEl.textContent = data.ok ? 'Online' : 'Unavailable';
    dot.classList.toggle('online', Boolean(data.ok));
  } catch {
    statusEl.textContent = 'Backend offline';
    dot.classList.remove('online');
  }
}

async function sendMessage(text) {
  const pending = addMessage('Nexus', 'Thinking…');
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Request failed');
    pending.lastChild.textContent = data.response || 'No response received.';
    if (speakResponses) speak(data.response || '');
  } catch (error) {
    pending.lastChild.textContent = error.message === 'Unauthorized'
      ? 'Nexus is private. Check the local access settings.'
      : 'I could not reach the Nexus brain. Check the local backend connection.';
    console.error(error);
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  addMessage('You', text);
  await sendMessage(text);
});

function speak(text) {
  if (!('speechSynthesis' in window)) {
    voiceStatus.textContent = 'Voice output unavailable in this browser';
    return;
  }
  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.98;
  utterance.pitch = 0.95;
  speechSynthesis.speak(utterance);
}

speakToggle.addEventListener('click', () => {
  speakResponses = !speakResponses;
  speakToggle.textContent = speakResponses ? '🔊 Read responses aloud: ON' : '🔊 Read responses aloud';
  voiceStatus.textContent = speakResponses ? 'Voice output: on' : 'Voice: ready';
});

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
  recognition = new SpeechRecognition();
  recognition.lang = 'en-CA';
  recognition.interimResults = false;
  recognition.continuous = false;
  recognition.onstart = () => { voiceStatus.textContent = 'Listening…'; mic.textContent = '⏺️'; };
  recognition.onend = () => { voiceStatus.textContent = 'Voice: ready'; mic.textContent = '🎙️'; };
  recognition.onerror = () => { voiceStatus.textContent = 'Voice input error'; mic.textContent = '🎙️'; };
  recognition.onresult = (event) => { input.value = event.results[0][0].transcript; input.focus(); };
  mic.addEventListener('click', () => { try { recognition.start(); } catch {} });
} else {
  mic.disabled = true;
  mic.title = 'Speech recognition is not supported in this browser';
  voiceStatus.textContent = 'Voice input unavailable in this browser';
}

checkHealth();