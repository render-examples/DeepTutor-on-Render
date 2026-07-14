# DeepTutor on Render

**One-click deploy of [DeepTutor](https://github.com/HKUDS/DeepTutor) — an agent-native learning workspace — as a single Docker web service, with every provider key kept environment-only.**

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/render-examples/DeepTutor-on-Render)

https://github.com/user-attachments/assets/7db869d6-4594-4993-b92e-3a0f5d043a85

---

DeepTutor connects tutoring, problem solving, quiz generation, research, visualization, and mastery practice in one extensible system (Chat, Partners, Co-Writer, Book, Knowledge Center, Memory, and more). This template deploys the all-in-one image — FastAPI backend + Next.js frontend running together under supervisord — as one Render web service backed by a persistent disk. For the full feature tour, see [**deeptutor.info**](https://deeptutor.info) and the [upstream repo](https://github.com/HKUDS/DeepTutor).

The [`render.yaml`](render.yaml) Blueprint declares every provider API key as a `sync: false` secret, so Render prompts for them at deploy time and stores them in its encrypted env-var store — never in the repo, never on disk.

## Secrets are environment-only

DeepTutor reads every provider key **exclusively** from environment variables:

- Keys are **never** written to the persistent disk, **never** entered in the Settings UI, and **never** returned to the browser. The Settings page shows a read-only **"Set via environment (`VAR_NAME`) ✓/✗"** indicator per provider.
- To add or rotate a key, set the env var in the Render **Environment** tab (or your host environment) and redeploy. See [`.env.example`](.env.example) for the full list of variable names.

## Architecture

```
                        ┌────────────────────────────────────────────┐
                        │ Render web service (Docker, plan: standard) │
                        │                                            │
   browser  ───HTTPS──► │  Next.js frontend  :3782  (health: / )     │
                        │        │  proxies /api and /ws in-process   │
                        │        ▼                                    │
                        │  FastAPI backend   :8001                    │
                        │        │                                    │
                        │        ▼                                    │
                        │  /app/data (persistent disk, 10 GB)         │
                        │  settings JSON · knowledge bases · memory   │
                        │  workspaces · logs   (NO secrets)           │
                        └────────────────────────────────────────────┘
```

A single container runs both processes under supervisord. The browser talks only to the frontend origin on **port 3782**; Next.js middleware forwards `/api/*` and `/ws/*` to the backend in-process. The disk at `/app/data` holds everything that should survive a redeploy — runtime settings, knowledge bases, per-user workspaces, memory, and logs. No secret is ever stored there.

## Prerequisites

**Required:**

- **At least one LLM provider key** (e.g. `OPENAI_API_KEY`). A single key covers that provider across LLM, embeddings, TTS/STT, and image generation.
  - For OpenAI, a least-privilege [**Restricted** key](https://platform.openai.com/api-keys) is enough. On the key's Permissions screen, grant only:
    - **List models → Read** — lets DeepTutor populate the model picker in **Settings → Models**.
    - **Model capabilities → Request** — the parent group that covers everything DeepTutor calls at runtime: Chat completions, Responses, Embeddings, Images, and Text-to-speech (plus audio transcription for STT). Leave the unused endpoints under it — Realtime, Moderations — at **None** if you expand the group.
    - Leave every other group at **None**
- **A Render account.** The Blueprint defaults to the `standard` plan (2 GB RAM) — RAG indexing and document parsing are memory-hungry, so `starter` may OOM.

**Optional** (leave blank to disable):

- **Web search** — `TAVILY_API_KEY`, `BRAVE_API_KEY`, `EXA_API_KEY`, `SERPER_API_KEY`, or `PERPLEXITY_API_KEY`.
- **Embedding / rerank** — `COHERE_API_KEY`, `JINA_API_KEY`.
- **Document parsing / RAG services** — `MINERU_API_TOKEN`, `PAGEINDEX_API_KEY`, `LIGHTRAG_API_KEY`.
- **Auth / PocketBase** — `AUTH_PASSWORD_HASH`, `POCKETBASE_ADMIN_PASSWORD` (also needs a one-time on-disk JSON edit to enable).

You don't need any optional keys to deploy — fill them in from the Render **Environment** tab later. See [`.env.example`](.env.example) for the complete list.

## Deploy

### Option 1: Deploy button

1. Click **Deploy to Render** above.
2. Pick a workspace and a service name.
3. Render prompts for the `sync: false` secrets. Paste at least one LLM key (e.g. `OPENAI_API_KEY`); leave the rest blank.
4. Confirm. Render reads `render.yaml`, builds the image, and creates the web service with a 10 GB disk at `/app/data`.

### Option 2: Manual Blueprint sync

1. Fork this repo.
2. In the Render Dashboard, go to **Blueprints** → **New Blueprint Instance** and point at your fork.
3. Confirm and apply.

## Post-deploy setup

Once the deploy is live, open the `.onrender.com` URL Render assigned.

- **Confirm the port.** The image serves the UI on **3782**; verify the web service routes there in the Render dashboard after the first deploy.
- **OpenAI works out of the box.** The app ships with a default **OpenAI** model profile (`gpt-5.6-luna` for chat, `text-embedding-3-small` for knowledge bases). Once `OPENAI_API_KEY` is set you can chat immediately — no manual Settings step required.
  - `gpt-5.6-luna` and the rest of the GPT-5 family (`gpt-5`, `gpt-5.1`, `gpt-5.6-*`) and the o-series (`o1`/`o3`/`o4`) are **reasoning models** that only accept the default sampling temperature — DeepTutor detects these and pins `temperature=1` automatically, so any configured chat temperature is ignored for them.
- **Configure other providers.** To use a different provider, open **Settings → Models** and add an LLM profile (base URL + model name). The API key is always sourced from the environment — you'll see the **"Set via environment ✓"** indicator; you never paste it here.
- **Azure OpenAI** resolves its key from `AZURE_OPENAI_API_KEY`, but a working profile also needs its non-secret **endpoint** (`base_url`), **API version**, and **deployment name** entered in Settings. (The `custom` / `custom_anthropic` providers have no fixed env var name and can't source a key from the environment — use a named provider if you need an env-only key.)
- **Add or rotate a key** any time from the Render **Environment** tab, then redeploy.

### Using the app

No document upload or knowledge base is required — with `OPENAI_API_KEY` set, plain chat works immediately against the default OpenAI profile. Each step below uses features that ship with the app.

1. **Chat (zero setup).** On the landing page you'll see the greeting *"What would you like to learn?"* and a composer reading *"How can I help you today?"*. Type a question and send — for example:

   > Explain gradient descent like I'm new to calculus, then give me one worked example.

2. **Switch capabilities from the composer.** The picker next to the composer offers the built-in modes — try one per demo:
   - **Solve** — multi-step reasoning: `Solve: a train leaves at 60 mph and another at 40 mph 30 min later; when do they meet?`
   - **Quiz** — auto-validated question generation: `Generate a 5-question quiz on photosynthesis with an answer key.`
   - **Visualize** — charts/diagrams/animations: `Visualize a bar chart of the planets by diameter.`
   - **Research** — multi-agent research (best with a web-search key such as `TAVILY_API_KEY`; see Prerequisites): `Research the current state of solid-state batteries.`

3. **Co-Writer (built-in sample).** Open **Co-Writer** and create a new document — it loads a bundled starter template ("DeepTutor Co-Writer") showcasing Markdown, tables, code, LaTeX, and Mermaid diagrams. Select any text and use the inline AI action to rewrite or extend it.

Each response streams live, so these all make for a quick visual demo without any file uploads or extra keys (Research aside).

## Demo mode (per-IP rate limits)

If you host a **public demo URL** where anyone can chat against *your* provider key, unbounded use means runaway spend. Demo mode caps per-visitor (per-IP) usage so the demo is safe to leave open. It is **off by default** — local and private forks are unaffected — and only takes effect when you set `DEMO=true`.

Set these under the Render **Environment** tab (or your host environment) on the demo service:

| Variable | Default | Purpose |
|---|---|---|
| `DEMO` | `false` | Master switch. Truthy: `1`, `true`, `yes`, `on` (case-insensitive). |
| `DEMO_RATE_LIMIT_PER_MIN` | `15` | Max spending requests per IP per minute. |
| `DEMO_RATE_LIMIT_PER_HOUR` | `200` | Max spending requests per IP per hour. |

When a visitor exceeds a limit, HTTP requests get a `429` with a `Retry-After` header and chat WebSocket messages get an error frame (the socket stays open, so the next allowed message works normally).

**Ephemeral history:** in demo mode chat history is kept in an in-memory SQLite database and never written to disk. A shared public demo would otherwise accumulate every visitor's conversations on the instance and — since the demo has no per-visitor auth boundary — surface them in other visitors' session lists. In-memory history is cleared on restart. (Same single-process caveat as above: the in-memory store is shared within one process; the `/api/v1/chat` REST loop, which the web demo does not use, still persists via its JSON store and is not gated.)

**What is guarded (v1):** the two chat WebSocket loops (`/chat`, `/ws`) — where the key is actually spent — plus an HTTP catch-all. The health check (`/`) and static outputs (`/api/outputs`) are exempt so the app keeps loading.

**Not yet guarded:** secondary spenders (`/question/*`, `/book`, notebook summaries, Co-Writer, voice TTS/STT). **Single-process only:** rate-limit buckets live in memory per process, which is right for a single-instance demo; running multiple instances multiplies the effective limit (each holds its own buckets). A shared store (e.g. Redis) would be the upgrade path.

## Cost

The Blueprint defaults to the `standard` web service plan plus a 10 GB persistent disk. LLM/provider usage is billed separately by each provider. Bump the plan if you hit OOM during heavy RAG indexing. See [Render pricing](https://render.com/pricing) for current rates.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Service returns 502 / won't load | Confirm the web service routes to port **3782** (not 8001) in the dashboard. |
| A provider shows "Set via environment ✗" | The env var is unset or misnamed. Check the exact name in [`.env.example`](.env.example), set it under **Environment**, and redeploy. |
| Out-of-memory during KB indexing | Bump the service plan above `standard`. |
| Browser blocked by CORS calling the API from another origin | The one-click deploy needs no CORS (the browser only talks to the frontend, which proxies the API). Only if you call the backend directly from a different origin: set `CORS_ORIGINS` to that origin, or `CORS_ALLOW_ALL=true` to trust any origin on a trusted network. |
| Auth / PocketBase won't enable | The password secrets are wired via env, but enabling login or PocketBase needs a one-time edit of `data/user/settings/*.json` on the disk. |

The `Dockerfile` is multi-stage; Render builds the final stage, which is the lean `production` image — no Docker **Target Stage** override is needed.

## License

DeepTutor is licensed under the [Apache License 2.0](LICENSE).
