# Progress & decisions log (SOCIOTHON 2026, deadline 18:00 IST)

Plan: A = local / no keys · B = ElevenLabs · C = GitHub + Render deploy · D = submission.
Newest entries at the bottom of each section.

## Status board
| Step | State | Notes |
|---|---|---|
| A1 Local bring-up | ✅ done | venv (py3.13), npm install, API + tools + plan run + `npm run build` all OK |
| A1b Fair routing baseline | ✅ done | was showing 0% saved; now ~22% (see D-1) |
| A2 Real coordinates (OSM) | ⏳ next | |
| A3 Sourced ₹/kg + CO₂e | ⏳ | |
| A4 UX polish | ⏳ | |
| A5 Weekday forecast | optional | |
| B ElevenLabs voice + agent | 🔑 waiting on API key | |
| C GitHub + Render | 🔑 waiting on accounts | |
| D README, demo script | ⏳ | |

## What YOU need to do in parallel
1. **ElevenLabs**: sign up, then Profile → API keys → create a key. Paste it to me (I'll put it in `.env`, never in git).
2. **Render**: sign up (GitHub login is easiest), then Account settings → API keys → create a key.
3. **GitHub**: create an **empty public** repo named `kabaad-line` and send me the URL.

## Decisions
- **D-1 (10:45) Routing baseline made fair.** Before: the baseline was 1 vehicle doing a nearest-neighbour round of every bin, ignoring load; the plan was 3 capacity-limited vehicles. Optimised km came out *higher*, so 0% saved. Now both sides use the same fleet, the same OR-Tools solver, tomorrow's forecast loads and up to 3 depot trips per collector (`TRIPS_PER_COLLECTOR`). The only difference is that the baseline empties every bin daily (status quo) while the plan visits only bins that need it. Result on seed data: 15.6 km → 12.1 km (**22.5% saved**), 11% in move-out mode. Defensible in Q&A.
- **D-2 (10:45) Multi-trip routing + workload balance.** Each collector gets up to 3 trips (unload at depot between trips), so bins are no longer dropped for capacity. Repeat trips carry a fixed solver penalty, so work spreads across collectors before anyone does a second trip. The penalty doesn't count toward reported km. Hindi briefing mentions the number of trips when there's more than one.
- **D-3** Python 3.13 locally (`.python-version` says 3.12, and Render uses 3.12.7 from `render.yaml`). All deps install fine on both.

## Log
- 10:21 Start. Repo had never been run: no venv, no node_modules, not a git repo, no `gh`/`ngrok`.
- 10:35 Backend up. All 3 voice tools verified with Devanagari/Hinglish input (`राजेंद्र भवन के पीछे वाला बिन` → Rajendra Bhawan, "ubal raha hai" → 110% overflow). Pickup + local plan run work.
- 10:50 Routing fix (D-1, D-2). Frontend builds clean.
