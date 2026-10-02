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

export async function onRequestPost({ request, env }) {
  if (!tokenIsValid(request, env)) {
    return json({ error: "Unauthorized" }, 401);
  }

  const apiUrl = (env.NEXUS_API_URL || "").replace(/\/$/, "");
  if (!apiUrl) return json({ error: "Nexus API is not configured" }, 503);

  let payload;
  try {
    payload = await request.json();
  } catch {
    return json({ error: "Invalid JSON" }, 400);
  }

  const message = payload?.message;
  if (typeof message !== "string" || !message.trim()) {
    return json({ error: "message must be non-empty text" }, 400);
  }
  if (message.length > 8000) {
    return json({ error: "Message exceeds Nexus input limit" }, 413);
  }

  try {
    const upstream = await fetch(`${apiUrl}/api/chat`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "authorization": `Bearer ${env.NEXUS_API_TOKEN}`,
      },
      body: JSON.stringify({ message }),
    });

    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { "content-type": "application/json; charset=utf-8" },
    });
  } catch {
    return json({ error: "Nexus brain is unavailable" }, 502);
  }
}
