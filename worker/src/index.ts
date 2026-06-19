// QPopCV notification proxy.
//
// The Python app POSTs { user_id, type } here. This worker validates the
// payload, applies rate limits, then forwards a formatted message to the
// real Discord webhook (held in env.DISCORD_WEBHOOK_URL — a wrangler secret,
// never in source).

interface Env {
  DISCORD_WEBHOOK_URL: string;
}

// Keep these strings in sync with qpopcv/messages.py.
const MESSAGES: Record<string, string> = {
  qpop: "<a:queuepopblink:1487592088148246559> Q Pop!",
  afk_warn: "<:afkzzz:1487591915120492634> AFK 28m. Move character (2m until logout)",
  afk_logout: "<:logoutalert:1487592229060083914> Logged out!",
  test: "is connected <:verify:1487594394008948816>",
};

const USER_ID_RE = /^\d{17,19}$/;

// Per-IP and per-user_id rate limits. In-memory; resets when the isolate
// recycles. For a production-grade limiter, swap for Durable Objects.
const RATE_LIMIT_WINDOW_MS = 60_000;
const MAX_PER_IP = 10;
const MAX_PER_USER = 5;

interface Bucket {
  count: number;
  resetAt: number;
}
const ipBuckets = new Map<string, Bucket>();
const userBuckets = new Map<string, Bucket>();

function take(map: Map<string, Bucket>, key: string, max: number): boolean {
  const now = Date.now();
  const b = map.get(key);
  if (!b || b.resetAt < now) {
    map.set(key, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
    return true;
  }
  if (b.count >= max) return false;
  b.count++;
  return true;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);

    if (req.method === "GET" && url.pathname === "/") {
      return new Response("qpopcv-proxy ok", { status: 200 });
    }

    if (req.method !== "POST" || url.pathname !== "/notify") {
      return json({ error: "not found" }, 404);
    }

    let payload: { user_id?: unknown; type?: unknown };
    try {
      payload = await req.json();
    } catch {
      return json({ error: "invalid json" }, 400);
    }

    const userId = String(payload.user_id ?? "").trim();
    const type = String(payload.type ?? "").trim();

    if (!USER_ID_RE.test(userId)) {
      return json({ error: "invalid user_id" }, 400);
    }
    if (!(type in MESSAGES)) {
      return json({ error: "invalid type" }, 400);
    }

    const ip = req.headers.get("cf-connecting-ip") ?? "unknown";
    if (!take(ipBuckets, ip, MAX_PER_IP)) {
      return json({ error: "rate limited (ip)" }, 429);
    }
    if (!take(userBuckets, userId, MAX_PER_USER)) {
      return json({ error: "rate limited (user)" }, 429);
    }

    if (!env.DISCORD_WEBHOOK_URL) {
      return json({ error: "proxy misconfigured" }, 500);
    }

    const content = `<@${userId}> ${MESSAGES[type]}`;
    const dr = await fetch(env.DISCORD_WEBHOOK_URL, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ content }),
    });

    if (!dr.ok) {
      return json({ error: "discord rejected", status: dr.status }, 502);
    }
    return json({ ok: true });
  },
};
