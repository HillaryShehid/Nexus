function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8' },
  });
}

export async function onRequestPost({ request, env }) {
  const apiUrl = (env.NEXUS_API_URL || '').replace(/\/$/, '');
  const token = env.NEXUS_API_TOKEN || '';
  if (!apiUrl || !token) return json({ error: 'Nexus API is not configured' }, 503);

  let payload;
  try {
    payload = await request.json();
  } catch {
    return json({ error: 'Invalid JSON' }, 400);
  }

  const message = payload && payload.message;
  if (typeof message !== 'string' || !message.trim()) return json({ error: 'message must be non-empty text' }, 400);
  if (message.length > 8000) return json({ error: 'Message exceeds Nexus input limit' }, 413);

  try {
    const upstream = await fetch(apiUrl + '/api/chat', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        authorization: 'Bearer ' + token,
      },
      body: JSON.stringify({ message }),
    });
    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: { 'content-type': 'application/json; charset=utf-8' },
    });
  } catch {
    return json({ error: 'Nexus brain is unavailable' }, 502);
  }
}