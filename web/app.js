const messages = document.querySelector('#messages');
const form = document.querySelector('#chat-form');
const input = document.querySelector('#input');
const statusEl = document.querySelector('#status');
const dot = document.querySelector('.dot');
const mic = document.querySelector('#mic');
const voiceStatus = document.querySelector('#voice-status');
const speakToggle = document.querySelector('#speak-toggle');

let voiceRoom = null;
let attachedAudio = [];

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
  const pending = addMessage('Nexus', '');
  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      body: JSON.stringify({ message: text }),
    });

    if (!response.ok) {
      let message = 'Request failed';
      try {
        const data = await response.json();
        message = data.error || message;
      } catch {}
      throw new Error(message);
    }

    if (!response.body) throw new Error('Streaming is not supported by this browser.');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split('\\n\\n');
      buffer = events.pop() || '';
      for (const event of events) {
        const line = event.split('\\n').find((item) => item.startsWith('data: '));
        if (!line) continue;
        const data = JSON.parse(line.slice(6));
        if (data.error) throw new Error(data.error);
        if (data.delta) {
          pending.lastChild.textContent += data.delta;
          messages.scrollTop = messages.scrollHeight;
        }
      }
    }

    if (!pending.lastChild.textContent) {
      pending.lastChild.textContent = 'No response received.';
    }
  } catch (error) {
    pending.lastChild.textContent = error.message === 'Unauthorized'
      ? 'Nexus is private. Check the local access settings.'
      : error.message || 'I could not reach the Nexus brain.';
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

function attachRemoteAudio(track) {
  const element = track.attach();
  element.autoplay = true;
  document.body.appendChild(element);
  attachedAudio.push(element);
}

function detachRemoteAudio() {
  for (const element of attachedAudio) {
    try {
      element.remove();
    } catch {}
  }
  attachedAudio = [];
}

async function connectLiveKit() {
  if (voiceRoom) return;

  if (!window.LivekitClient) {
    throw new Error('LiveKit client library did not load.');
  }

  voiceStatus.textContent = 'Starting LiveKit voice…';
  mic.textContent = '⏹️';

  const tokenResponse = await fetch('/api/livekit/token', {
    method: 'POST',
    credentials: 'same-origin',
  });
  const tokenData = await tokenResponse.json();

  if (!tokenResponse.ok) {
    throw new Error(tokenData.error || 'Could not start LiveKit voice.');
  }

  const room = new LivekitClient.Room({
    adaptiveStream: true,
    dynacast: true,
  });

  room.on(LivekitClient.RoomEvent.TrackSubscribed, (track) => {
    if (track.kind === LivekitClient.Track.Kind.Audio) {
      attachRemoteAudio(track);
    }
  });

  room.on(LivekitClient.RoomEvent.TrackUnsubscribed, (track) => {
    track.detach().forEach((element) => element.remove());
  });

  room.on(LivekitClient.RoomEvent.Disconnected, () => {
    disconnectLiveKit(false);
  });

  await room.connect(tokenData.server_url, tokenData.participant_token);
  await room.localParticipant.setMicrophoneEnabled(true);

  voiceRoom = room;
  voiceStatus.textContent = 'LiveKit voice: listening';
}

function disconnectLiveKit(updateStatus = true) {
  if (!voiceRoom) return;

  try {
    voiceRoom.localParticipant.setMicrophoneEnabled(false);
    voiceRoom.disconnect();
  } catch (error) {
    console.error(error);
  }

  voiceRoom = null;
  detachRemoteAudio();
  mic.textContent = '🎙️';

  if (updateStatus) {
    voiceStatus.textContent = 'Voice: off';
  }
}

mic.addEventListener('click', async () => {
  if (voiceRoom) {
    disconnectLiveKit();
    return;
  }

  try {
    await connectLiveKit();
  } catch (error) {
    disconnectLiveKit(false);
    voiceStatus.textContent = error.message || 'Could not start voice';
    console.error(error);
  }
});

speakToggle.textContent = '🗣️ LiveKit voice';

checkHealth();
