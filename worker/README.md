# QPopCV notification proxy

A tiny Cloudflare Worker that sits between the QPopCV desktop app and the
community Discord webhook. The real webhook URL lives only as a worker
secret — it is never shipped in source, in the .exe, or in git.

## Why

Originally the app POSTed straight to a Discord webhook whose URL was
baked into `config.json`. Anyone cloning the repo could (and did) grab
that URL and spam the channel. This proxy moves the secret server-side
so abuse is rate-limited and the URL can be rotated without rebuilding
the app.

## Deploy (one-time)

```bash
cd worker
npm install -g wrangler         # if you don't have it
wrangler login
wrangler secret put DISCORD_WEBHOOK_URL
# paste the real Discord webhook URL when prompted
wrangler deploy
```

Wrangler will print the worker URL (e.g. `https://qpopcv-proxy.<your-subdomain>.workers.dev`).

## Wire the app to it

Edit `qpopcv/config.py` and replace the `PROXY_URL` placeholder with
`https://qpopcv-proxy.<your-subdomain>.workers.dev/notify`. Bump the
patch version and ship a new build.

## Rotate the webhook (if it leaks again)

1. Delete the old webhook in Discord.
2. Create a fresh webhook on the same channel.
3. `wrangler secret put DISCORD_WEBHOOK_URL` and paste the new URL.

No app rebuild required — the proxy URL is unchanged.

## Endpoint

`POST /notify`

```json
{ "user_id": "695333359080964166", "type": "qpop" }
```

Valid `type` values: `qpop`, `afk_warn`, `afk_logout`, `test`. Returns
`{ ok: true }` on success.

## Rate limits

In-memory per-isolate buckets (60 s window):

- 10 requests per IP
- 5 requests per Discord user_id

If abuse escalates, replace with a Durable Object–backed limiter.
