# Kabaad Line · कबाड़ लाइन

**Voice-first waste operations for the people who actually move campus waste.**
Sanitation staff and kabadiwalas report full bins and log what they collected by *talking in Hindi*. Students request scrap pickups. Every night a Render Workflow forecasts bin fill, solves the collection routes, and generates a spoken Hindi briefing for each collector.

SOCIOTHON 2026 · IIT Roorkee · Smart & Sustainable Waste Management

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

Press **Plan tomorrow** on the dashboard. With no Render keys it runs the same pipeline in-process.
Reseed any time: `python -m server.seed`.

Try the voice tools without ElevenLabs:
```bash
curl -X POST localhost:8000/tools/report_bin_status -H "X-Tool-Secret: change-me" -H "Content-Type: application/json" \
  -d '{"location_name":"राजेंद्र भवन के पीछे वाला बिन","fill_level":"ubal raha hai"}'
```

## How it fits together

```
 Collector (voice, Hindi) ──► ElevenLabs Agent ──webhook tools──► FastAPI  /tools/*
 Student (web form)       ──────────────────────────────────────► FastAPI  /api/pickups
 Dashboard (React)        ◄──────────────────────────────────────  FastAPI  /api/*
                                                                     │  POST /api/plan/run
                                                                     ▼
                              Render Workflow  plan_tomorrow
                                ├─ load_state           (GET /internal/state)
                                ├─ forecast_fill
                                ├─ select_stops         forecast ≥75% + voice overflows + pickups
                                ├─ solve_routes         OR-Tools capacitated VRP
                                ├─ publish_routes       (POST /internal/plan-runs/{id}/result)
                                └─ synthesize_briefing  × N collectors in parallel → ElevenLabs TTS
```

| Path | What |
|---|---|
| `server/main.py` | API, ElevenLabs tool endpoints, workflow callbacks, local fallback |
| `server/planner.py` | Pure planning logic (forecast, stop selection, VRP, baseline, Hindi script) |
| `server/workflows.py` | Render Workflow tasks wrapping the planner |
| `server/matching.py` | Fuzzy Hindi/English/Devanagari location matching |
| `server/config.py` | Materials, ₹/kg rates, CO₂ factors, planning knobs |
| `server/seed.py` | Campus locations + 14 days of **simulated** history |
| `voice/` | Agent system prompt + tool setup guide |
| `web/` | React dashboard, collector page, student request page |

## Deploy on Render

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
| Render Workflow execution and parallel TTS briefings | Collector names and vehicle capacities |

Every simulated number is tagged **Simulated** in the UI.

## Impact metrics we report
- Route km saved vs a fixed daily round visiting every bin (+ fuel and CO₂ saved). The comparison is like for like: same collectors, same vehicle capacities, same 3-trip limit, same forecast loads, same OR-Tools solver. The only difference is that the status-quo round empties every bin, while Kabaad Line visits only bins forecast ≥75% full, voice-reported overflows and student pickups. Repeat trips carry a solver penalty, so work is spread across collectors.
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
| Coordinates | — | © OpenStreetMap contributors via the Overpass API, queried 24 Oct 2026 |

## Credits
ElevenLabs (Agents + TTS), Render (Web Services, Postgres, Workflows), Google OR-Tools, FastAPI, SQLAlchemy, RapidFuzz, React, Vite, Tailwind CSS, Leaflet + OpenStreetMap (tiles and building positions via Overpass), Recharts, US EPA WARM.
