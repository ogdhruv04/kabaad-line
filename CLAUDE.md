# Kabaad Line — brief for Claude Code

SOCIOTHON 2026 (IIT Roorkee). **Hard deadline 6:00 PM IST today.** Working, polished, demoable beats complete.
Judging, 25% each: Impact · Technical execution · UX & polish · Theme alignment.
Also targeting the **ElevenLabs track** (voice must be core and clearly shown) and the **Render track** (deployed on Render, uses Render Workflows, public GitHub + live URL + demo video).

## Product in one line
Collectors (safai staff, kabadiwalas) talk to a Hindi voice agent to report bins and log collections; students request scrap pickups; a Render Workflow plans tomorrow's routes and generates spoken Hindi briefings. Users: collector (voice only), student (web form), supervisor (dashboard).

## Current state — this starter already works end to end locally
- `server/` FastAPI + SQLAlchemy (SQLite locally, Postgres on Render). Auto-seeds on first start.
- `/tools/report_bin_status`, `/tools/log_collection`, `/tools/get_my_route` — ElevenLabs webhook tools, header `X-Tool-Secret`. Hindi/Hinglish/Devanagari fuzzy location matching in `matching.py`.
- `planner.py` pure functions on JSON dicts: forecast → select stops → OR-Tools CVRP → baseline → Hindi briefing.
- `workflows.py` Render Workflow tasks wrapping the planner; `/api/plan/run` triggers it, or runs the same pipeline in a thread when `RENDER_API_KEY`/`WORKFLOW_SLUG` aren't set.
- `web/` React 19 + Vite + Tailwind v4 + react-leaflet + recharts: Dashboard, Collector (ElevenLabs widget + route + audio), Request (EN/HI).

## Render SDK facts (verified against installed render==1.4.0 — don't "fix" these)
- Package is `render` (`render_sdk` is a deprecated shim). `from render import Workflows, TaskContext, Retry, Render`.
- Every task's first parameter is `ctx: TaskContext`. Subtask: `await ctx.run(task, *args)`. Parallel: `asyncio.gather(ctx.run(...), ...)`.
- `Retry(max_retries, wait_duration_ms, backoff_scaling)`; `@app.task(timeout_seconds=..., plan=..., retry=...)`.
- Start command: `render-workflows server.workflows:app`. Trigger: `Render().workflows.start_task("<slug>/<task>", {...})` (uses `RENDER_API_KEY`).
- Args/results must be JSON-serialisable.

## Rules
- **Honesty (hackathon rule 7):** seeded readings/collections are simulated → keep the "Simulated" badges. Voice, pickups, routing, workflow runs and TTS are real.
- **Render track dropped (24 Oct, ~11:20):** Render signup failed (no verification email). Demo runs locally + cloudflared tunnel for the ElevenLabs webhooks. Workflow code stays; don't claim a Render deploy anywhere.
- Secrets only in env vars. Never block a web request on TTS or VRP.
- Keep `main` deployable. Acknowledge third-party tools in README.

## Highest-value next steps (in order)
1. Fix real coordinates for `server/seed.py` LOCATIONS from Google Maps; add/remove bhawans to match campus.
2. Create the ElevenLabs agent (`voice/AGENT_SETUP.md`), test the three tools via ngrok, put the agent ID in `web/.env`.
3. Deploy to Render (README), create the Workflow service, confirm "engine: Render Workflow" in the dashboard.
4. Replace ₹/kg and CO₂e placeholders in `config.py` with sourced numbers; cite in README.
5. UX polish: live voice feed animation on Collector page, mobile check, an "impact this week" story card.
6. Stretch: weekday-aware forecast; supervisor "missed pickup" alerts read out by voice; Twilio phone line.
