# Kabaad Line · कबाड़ लाइन

**Voice-first waste operations for the people who actually move campus waste.**
Sanitation staff and kabadiwalas report full bins and log what they collected by *talking in Hindi*. Students request scrap pickups. A planning pipeline forecasts bin fill, solves the collection routes, and generates a spoken Hindi briefing for each collector. It runs in-process today and is written as Render Workflow tasks, ready to deploy.

SOCIOTHON 2026 · IIT Roorkee · Smart & Sustainable Waste Management

### ▶ [Watch the demo video](https://drive.google.com/file/d/1Za_-Vdfquom2p_Kz_Diy3M2gC3gRELX5/view?usp=sharing)

## At a glance
- **Who it's for:** safai staff and kabadiwalas, the informal workforce that actually moves campus waste and mostly doesn't use apps. They use it **by voice, in Hindi or Hinglish**: report a full bin, log "12 kilo gatta", ask "ab kahan jaana hai?". Students request scrap pickups on the web; supervisors watch a live dashboard.
- **What the voice does:** an ElevenLabs agent with a native Hindi voice calls our webhook tools. Every log updates the map, ticks the stop off that collector's route, closes any student pickup there, and the agent replies with the ₹ value of what they collected and their **next stop**.
- **How routes are planned:** a weekday-aware fill forecast picks only the bins that need a visit. OR-Tools then solves a multi-trip capacitated VRP **balanced so every collector gets a similar shift**, and each collector gets a spoken Hindi briefing. It runs on demand and automatically every night at 21:00 IST.
- **Impact, measured honestly:** tomorrow's plan on the seeded campus is **~30% fewer route-km** than the fixed every-bin round (same crew, same trucks, same solver). Shifts are 60/60/53 min, where the unbalanced plan gave 72/58/26. ₹ and CO₂e come from a published kabadi rate list and US EPA WARM factors. Simulated history is labelled **Simulated** everywhere.

---

## Run it locally (5 min)

```bash
# backend (repo root)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn server.main:app --reload          # http://localhost:8000  (auto-seeds on first start)

# frontend (new terminal)
cd web && npm install && cp .env.example .env && npm run dev    # http://localhost:5173
```

Or start both servers at once with `./run-local.sh`. Press **Plan tomorrow** on the dashboard. With no Render keys it runs the same pipeline in-process (this is how the demo runs).

### Letting the voice agent reach your laptop
ElevenLabs' servers call the `/tools/*` webhooks, so the backend needs a public URL. Without a deploy, use a quick tunnel and repoint the agent's tools at it:
```bash
~/.local/bin/cloudflared tunnel --no-autoupdate --url http://localhost:8000   # prints https://<random>.trycloudflare.com
python -m voice.create_agent --base-url https://<random>.trycloudflare.com --update
```
The tunnel URL changes every time it restarts, so re-run the `--update` line each time.
Reseed any time: `python -m server.seed`.

### Voice agent (ElevenLabs)
```bash
python -m voice.create_agent --hindi-voices                       # pick a Hindi voice → ELEVENLABS_VOICE_ID in .env
python -m voice.create_agent --base-url https://<public-backend-url>       # creates the 3 webhook tools + the Hindi agent
python -m voice.create_agent --base-url https://<new-url> --update        # repoint tools later
```
It prints the agent ID; put it in `web/.env` as `VITE_ELEVENLABS_AGENT_ID`. The Collector page talks to the agent inline over WebRTC using `@elevenlabs/react`: a big mic button, a live Hindi transcript, and a receipt chip each time the agent calls a tool. `collector_name` is passed as a dynamic variable and bound straight into the tool calls, so the LLM never guesses who is speaking. Manual setup is described in `voice/AGENT_SETUP.md`.

Try the voice tools without ElevenLabs:
```bash
curl -X POST localhost:8000/tools/report_bin_status -H "X-Tool-Secret: dev-secret" -H "Content-Type: application/json" \
  -d '{"location_name":"राजेंद्र भवन के पीछे वाला बिन","fill_level":"ubal raha hai"}'
```

## How it fits together

```
 Collector (voice, Hindi) ──► ElevenLabs Agent ──webhook tools──► FastAPI  /tools/*
 Student (web form)       ──────────────────────────────────────► FastAPI  /api/pickups
 Dashboard (React)        ◄──────────────────────────────────────  FastAPI  /api/*
                                                                     │  POST /api/plan/run
                                                                     ▼
                     plan_tomorrow  (in-process thread; Render Workflow tasks when deployed)
                                ├─ load_state           (GET /internal/state)
                                ├─ forecast_fill
                                ├─ select_stops         forecast ≥75% + voice overflows + pickups
                                ├─ solve_routes         OR-Tools multi-trip CVRP, balanced shifts
                                ├─ publish_routes       (POST /internal/plan-runs/{id}/result)
                                └─ synthesize_briefing  × N collectors in parallel → ElevenLabs TTS
```

Each step reports back as it finishes, so the dashboard lights up the pipeline live. In the demo the pipeline runs in a background thread. `server/workflows.py` has the same steps as durable Render Workflow tasks (with retries, and TTS fanned out in parallel per collector) for when it's deployed; they report through `POST /internal/plan-runs/{id}/step`.

**Who controls what.**
| Role | Can do | What it changes |
|---|---|---|
| Collector (voice, Hindi) | "X ka dibba bhar gaya" | Sets the bin's fill level. Overflows force the bin into the next plan. |
| | "X se 12 kilo gatta uthaya" | Logs a collection (₹ value, today's total), marks the bin emptied, **ticks that stop off their route**, closes any student pickup there, and the agent **announces the next stop** |
| | "Ab kahan jaana hai?" | Reads the **remaining** stops |
| Student (web, EN/HI) | Pickup request or overflow report | Becomes a guaranteed stop in the next plan. The status goes requested → on tomorrow's route → collected ✓ |
| Supervisor (dashboard) | "Plan tomorrow", move-out mode | Re-plans everyone's routes. The same plan also runs **automatically at 21:00 IST** (`AUTO_PLAN_AT_IST`) |

**Planning details.**
- *Forecast:* each bin's fill rate is learned from the last 7 days of readings. It is weekday-aware, so hostels fill faster at weekends.
- *Stop selection:* a bin is a stop if forecast ≥75% full, voice-reported overflowing, or has a student pickup request.
- *Routing:* OR-Tools capacitated VRP, one vehicle per collector, with optional unload-at-depot nodes (the reload pattern) for up to 3 trips. A shift-time dimension counts driving at 12 km/h, 4 min per stop plus 6 min per 100 kg loaded, and 12 min to unload. A global span cost keeps the longest shift short, so **work is split evenly**: on the seed data, shifts come out at 60/60/53 min instead of 72/58/26, for +1.2 km in total. Move-out mode gives 2 trips each and shifts within 5 min of each other.
- *Briefing:* a Hindi briefing per collector, with place names in Devanagari so the voice pronounces them naturally.

| Path | What |
|---|---|
| `server/main.py` | API, ElevenLabs tool endpoints, workflow callbacks, local fallback |
| `server/planner.py` | Pure planning logic (forecast, stop selection, VRP, baseline, Hindi script) |
| `server/workflows.py` | Render Workflow tasks wrapping the planner |
| `server/matching.py` | Fuzzy Hindi/English/Devanagari location matching |
| `server/config.py` | Materials, ₹/kg rates, CO₂ factors, planning knobs |
| `server/seed.py` | Campus locations + 14 days of **simulated** history |
| `voice/` | Agent system prompt, `create_agent.py` (creates/updates the agent + tools via API), manual setup guide |
| `web/` | React dashboard, collector page (inline voice agent), student request page |
| `run-local.sh` | Starts the API and web app together |
| `DEMO.md` · `PROGRESS.md` | Demo script · build log with every decision and why |

## Deploy on Render (optional; not deployed for the hackathon demo)

1. Push to a **public** GitHub repo (the Render track requires it).
2. Render → **New → Blueprint** → this repo. Creates `kabaad-api`, `kabaad-web`, `kabaad-db`. Fill the `sync: false` env vars.
3. Render → **New → Workflow** → same repo:
   - Build: `pip install -r requirements.txt`
   - Start: `render-workflows server.workflows:app`
   - Env: `BACKEND_URL=https://kabaad-api.onrender.com`, `TOOL_SHARED_SECRET`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`
4. On `kabaad-api` set `WORKFLOW_SLUG` = the workflow service's name, and `RENDER_API_KEY` (Account settings → API keys).
5. Dashboard → **Plan tomorrow** should now say *engine: Render Workflow*; open the run in the Render dashboard to show the task tree in the demo.

Workflows is in beta, so check the Render dashboard/docs if a menu name differs. SDK facts used here (verified against `render==1.4.0`): package is `render`, every task takes `ctx` first, subtasks run via `await ctx.run(task, ...)`, trigger with `Render().workflows.start_task("<slug>/plan_tomorrow", {...})`.

## What's real vs simulated (hackathon rule 7)

| Real, working live | Simulated / placeholder |
|---|---|
| Voice reports and collection logs via ElevenLabs agent | Bin fill-level history ("sensor_sim") |
| Student pickup requests and overflow reports | 14 days of past collections (KPI history) |
| Forecast, stop selection, OR-Tools routing, baseline comparison | Depot position and Azad Bhawan pin (approximate; others from OpenStreetMap) |
| Planning runs (in-process, plus nightly auto-plan) and Hindi TTS briefings | Collector names and vehicle capacities |
| Route progress, next-stop guidance and pickup status from voice logs | Shift-time model parameters (see assumptions) |

Every simulated number is tagged **Simulated** in the UI.

## Impact metrics we report
- Route km saved vs a fixed daily round visiting every bin (+ fuel and CO₂ saved). The comparison is like for like: same collectors, same vehicle capacities, same 3-trip limit, same forecast loads, same OR-Tools solver. The only difference is that the status-quo round empties every bin, while Kabaad Line visits only bins forecast ≥75% full, voice-reported overflows and student pickups. Both sides use the same shift-balanced model.
- Workload fairness: estimated shift minutes per collector, and the gap between the longest and shortest shift.
- Share of collected weight diverted from landfill; ₹ value recovered for collectors.
- Multilayer-packaging (MLP) share, the non-recyclable fraction to target.
- Voice reports per day, a proxy for how much of the informal workforce is now "on the map".

## Sources & assumptions
| Number | Value | Source |
|---|---|---|
| CO₂e avoided per kg recycled | cardboard 3.46, PET 1.15, HDPE 0.84, metal 2.02, glass 0.31 kg/kg | US EPA WARM v16 (Dec 2023), *Containers, Packaging & Non-Durable Goods Materials* chapter, Exhibits 1-14, 2-17, 3-17, 5-11 ([PDF](https://www.epa.gov/system/files/documents/2023-12/warm_containers_packaging_and_non-durable_goods_materials_v16_dec.pdf)). MTCO₂e/short ton × 1.1023. Metal uses steel cans, not aluminium (10.06), to stay conservative. E-waste, organic, MLP and mixed are not credited. |
| ₹ per kg | carton 6, PET 10, hard plastic 5, tin/metal 15, e-waste 10, glass 1 | [TheKabadiwala Delhi rate list](https://www.thekabadiwala.com/scrap-rates/delhi), accessed 24 Oct 2026. These are doorstep prices paid to households, so what a collector gets from a dealer is higher and our ₹ figures are conservative. Glass isn't on the list (our estimate). Roorkee rates may differ. |
| Diesel CO₂ | 2.68 kg/L | IPCC 2006 Guidelines default for diesel (74.1 t CO₂/TJ) |
| Vehicle fuel use | 0.08 L/km | Assumption: small diesel tipper, ~12.5 km/L in stop-start duty |
| Bin bulk density | 0.12 kg/L | Assumption for loose, mostly dry campus waste |
| Road distance | 1.35 × straight line | Assumption (campus road grid) |
| Shift time | 12 km/h, 4 min per stop + 6 min per 100 kg, 12 min to unload | Assumptions for a small cart/tipper; used only to balance work |
| Coordinates | — | © OpenStreetMap contributors via the Overpass API, queried 24 Oct 2026 |

## Credits
ElevenLabs (Agents + TTS), Render Workflows SDK (pipeline written for it; not deployed), Cloudflare quick tunnels, Google OR-Tools, FastAPI, SQLAlchemy, RapidFuzz, React, Vite, Tailwind CSS, Leaflet + OpenStreetMap (tiles and building positions via Overpass), Recharts, US EPA WARM.
