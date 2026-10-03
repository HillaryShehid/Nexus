const messages = document.querySelector('#messages');
const form = document.querySelector('#chat-form');
const input = document.querySelector('#input');
const statusEl = document.querySelector('#status');
const dot = document.querySelector('.dot');
const mic = document.querySelector('#mic');
const voiceStatus = document.querySelector('#voice-status');
const speakToggle = document.querySelector('#speak-toggle');

let realtime = null;
let realtimeAudio = null;
let assistantTranscript = '';

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

function sendRealtimeEvent(event) {
  if (!realtime?.dataChannel || realtime.dataChannel.readyState !== 'open') {
    throw new Error('Realtime voice is not connected.');
  }
  realtime.dataChannel.send(JSON.stringify(event));
}

async function handleNexusToolCall(event) {
  let args;
  try {
    args = JSON.parse(event.arguments || '{}');
  } catch {
    args = {};
  }

  const request = typeof args.request === 'string' ? args.request.trim() : '';
  if (!request) {
    sendRealtimeEvent({
      type: 'conversation.item.create',
      item: {
        type: 'function_call_output',
        call_id: event.call_id,
        output: JSON.stringify({ error: 'No user request was captured.' }),
      },
    });
    sendRealtimeEvent({ type: 'response.create' });
    return;
  }

  voiceStatus.textContent = 'Nexus is thinking…';
  addMessage('You', request);

  try {
    const response = await fetch('/api/realtime/brain', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Nexus brain request failed');

    sendRealtimeEvent({
      type: 'conversation.item.create',
      item: {
        type: 'function_call_output',
        call_id: event.call_id,
        output: JSON.stringify({ response: data.response || '' }),
      },
    });
    sendRealtimeEvent({ type: 'response.create' });
  } catch (error) {
    console.error(error);
    sendRealtimeEvent({
      type: 'conversation.item.create',
      item: {
        type: 'function_call_output',
        call_id: event.call_id,
        output: JSON.stringify({
          error: 'The Nexus brain could not complete this request safely.',
        }),
      },
    });
    sendRealtimeEvent({ type: 'response.create' });
  }
}

function handleRealtimeEvent(event) {
  switch (event.type) {
    case 'session.created':
    case 'session.updated':
      voiceStatus.textContent = 'Realtime voice: ready';
      break;

    case 'input_audio_buffer.speech_started':
      voiceStatus.textContent = 'Listening…';
      break;

    case 'input_audio_buffer.speech_stopped':
      voiceStatus.textContent = 'Thinking…';
      break;

    case 'response.output_audio_transcript.delta':
      assistantTranscript += event.delta || '';
      voiceStatus.textContent = 'Nexus is speaking…';
      break;

    case 'response.output_audio_transcript.done':
      if (assistantTranscript.trim()) {
        addMessage('Nexus', assistantTranscript.trim());
      }
      assistantTranscript = '';
      break;

    case 'response.function_call_arguments.done':
      if (event.name === 'nexus_brain') {
        handleNexusToolCall(event).catch(console.error);
      }
      break;

    case 'response.done':
      if (event.response?.status === 'failed') {
        voiceStatus.textContent = 'Voice response failed';
      } else {
        voiceStatus.textContent = 'Realtime voice: ready';
      }
      break;

    case 'error':
      console.error('Realtime error:', event);
      voiceStatus.textContent = event.error?.message || 'Realtime voice error';
      break;

    default:
      break;
  }
}

async function connectRealtime() {
  if (realtime) return;

  if (!window.RTCPeerConnection || !navigator.mediaDevices?.getUserMedia) {
    throw new Error('This browser does not support the required WebRTC microphone APIs.');
  }

  voiceStatus.textContent = 'Starting realtime voice…';
  mic.textContent = '⏹️';

  const tokenResponse = await fetch('/api/realtime/token', {
    method: 'POST',
    credentials: 'same-origin',
  });
  const tokenData = await tokenResponse.json();
  if (!tokenResponse.ok) {
    throw new Error(tokenData.error || 'Could not start the Realtime session.');
  }

  const pc = new RTCPeerConnection();
  const dataChannel = pc.createDataChannel('oai-events');
  const audio = new Audio();
  audio.autoplay = true;
  realtimeAudio = audio;

  pc.ontrack = (event) => {
    audio.srcObject = event.streams[0];
  };

  pc.onconnectionstatechange = () => {
    if (pc.connectionState === 'connected') {
      voiceStatus.textContent = 'Realtime voice: listening';
    } else if (['failed', 'disconnected', 'closed'].includes(pc.connectionState)) {
      disconnectRealtime(false);
    }
  };

  dataChannel.addEventListener('open', () => {
    voiceStatus.textContent = 'Realtime voice: listening';
  });
  dataChannel.addEventListener('message', (event) => {
    try {
      handleRealtimeEvent(JSON.parse(event.data));
    } catch (error) {
      console.error('Invalid Realtime event:', error);
    }
  });

  const microphone = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });
  microphone.getTracks().forEach((track) => pc.addTrack(track, microphone));

  // The browser receives model audio on a negotiated WebRTC track.
  pc.addTransceiver('audio', { direction: 'recvonly' });

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  const sdpResponse = await fetch('https://api.openai.com/v1/realtime/calls', {
    method: 'POST',
    headers: {
      Authorization: 'Bearer ' + tokenData.value,
      'Content-Type': 'application/sdp',
    },
    body: offer.sdp,
  });

  if (!sdpResponse.ok) {
    microphone.getTracks().forEach((track) => track.stop());
    pc.close();
    throw new Error('OpenAI could not establish the Realtime WebRTC session.');
  }

  const answer = await sdpResponse.text();
  await pc.setRemoteDescription({ type: 'answer', sdp: answer });

  realtime = { pc, dataChannel, microphone };
}

function disconnectRealtime(updateStatus = true) {
  if (!realtime) return;

  realtime.microphone?.getTracks().forEach((track) => track.stop());
  realtime.dataChannel?.close();
  realtime.pc?.close();
  realtime = null;

  if (realtimeAudio) {
    realtimeAudio.srcObject = null;
    realtimeAudio = null;
  }

  mic.textContent = '🎙️';
  if (updateStatus) voiceStatus.textContent = 'Voice: off';
}

mic.addEventListener('click', async () => {
  if (realtime) {
    disconnectRealtime();
    return;
  }

  try {
    await connectRealtime();
  } catch (error) {
    disconnectRealtime(false);
    voiceStatus.textContent = error.message || 'Could not start voice';
    console.error(error);
  }
});

// This is now the realtime speech-to-speech control, not a TTS toggle.
speakToggle.textContent = '🗣️ Realtime voice';

checkHealth();
