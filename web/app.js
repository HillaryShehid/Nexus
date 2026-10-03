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
let speechRun = 0;
let currentAudio = null;

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
    if (speakResponses) {
      try {
        await speak(data.response || '');
      } catch (error) {
        voiceStatus.textContent = 'Voice output error';
        console.error(error);
      }
    }
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

function splitSpeech(text, maxChars = 900) {
  const chunks = [];
  let current = '';
  for (const paragraph of String(text || '').split(/\\n/)) {
    for (const word of paragraph.trim().split(/\\s+/)) {
      if (!word) continue;
      const candidate = current ? current + ' ' + word : word;
      if (candidate.length <= maxChars) {
        current = candidate;
      } else {
        if (current) chunks.push(current);
        current = word;
      }
    }
    if (current) {
      chunks.push(current);
      current = '';
    }
  }
  return chunks;
}

async function speak(text) {
  const run = ++speechRun;
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.src = '';
    currentAudio = null;
  }
  const chunks = splitSpeech(text);
  if (!chunks.length) return;

  voiceStatus.textContent = 'Generating Nexus voice…';
  for (const chunk of chunks) {
    if (run !== speechRun) return;
    const response = await fetch('/api/speech', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: chunk }),
    });
    if (!response.ok) throw new Error('Nexus speech generation failed');
    const blob = await response.blob();
    if (run !== speechRun) return;

    const audio = new Audio(URL.createObjectURL(blob));
    currentAudio = audio;
    voiceStatus.textContent = 'Nexus is speaking…';
    await new Promise((resolve, reject) => {
      audio.onended = resolve;
      audio.onerror = reject;
      audio.play().catch(reject);
    });
    URL.revokeObjectURL(audio.src);
    currentAudio = null;
  }
  if (run === speechRun) voiceStatus.textContent = 'Voice: ready';
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