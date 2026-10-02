function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8' },
  });
}

export async function onRequestGet({ env }) {
  const apiUrl = (env.NEXUS_API_URL || '').replace(/\/$/, '');
  const token = env.NEXUS_API_TOKEN || '';
  if (!apiUrl || !token) return json({ ok: false, error: 'Nexus API is not configured' }, 503);

  try {
    const upstream = await fetch(apiUrl + '/api/health', {
      headers: { authorization: 'Bearer ' + token },
    });
    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: { 'content-type': 'application/json; charset=utf-8' },
    });
  } catch {
    return json({ ok: false, error: 'Nexus brain is unavailable' }, 502);
  }
}