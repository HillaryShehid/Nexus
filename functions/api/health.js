function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function tokenIsValid(request, env) {
  const expected = env.NEXUS_API_TOKEN;
  const authorization = request.headers.get("Authorization") || "";
  return Boolean(expected && authorization === `Bearer ${expected}`);
}

export async function onRequestGet({ request, env }) {
  if (!tokenIsValid(request, env)) return json({ error: "Unauthorized" }, 401);

  const apiUrl = (env.NEXUS_API_URL || "").replace(/\/$/, "");
  if (!apiUrl) return json({ ok: false, error: "Nexus API is not configured" }, 503);

  try {
    const upstream = await fetch(`${apiUrl}/api/health`, {
      headers: { "authorization": `Bearer ${env.NEXUS_API_TOKEN}` },
    });
    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { "content-type": "application/json; charset=utf-8" },
    });
  } catch {
    return json({ ok: false, error: "Nexus brain is unavailable" }, 502);
  }
}
