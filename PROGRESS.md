# Progress & decisions log (SOCIOTHON 2026, deadline 18:00 IST)

Plan: A = local / no keys · B = ElevenLabs · C = GitHub + Render deploy · D = submission.
Newest entries at the bottom of each section. Times are IST.

## Status board
| Step | State | Notes |
|---|---|---|
| A1 Local bring-up | ✅ done | venv (py3.13), npm install, API + tools + plan run + `npm run build` all OK |
| A1b Fair routing baseline | ✅ done | was showing 0% saved; now ~22% (see D-1) |
| A2 Real coordinates (OSM) | ✅ done | 24 of 26 pins from OSM; depot + Azad approx (D-4) |
| A3 Sourced ₹/kg + CO₂e | ✅ done | EPA WARM v16 + TheKabadiwala list; README Sources table (D-5) |
| A4 UX polish | ✅ done | live pipeline steps, impact card, inline voice panel + transcript, feed flash, mobile fixes (D-6..D-8) |
| A5 Weekday forecast | ✅ done | weekend vs weekday fill rate (D-9) |
| B ElevenLabs voice + agent | 🔑 waiting on API key | |
| C GitHub + Render | 🔑 waiting on accounts | |
| D README, demo script | ⏳ | |

## What YOU need to do in parallel
1. **ElevenLabs**: sign up, then Profile → API keys → create a key. Paste it to me (I'll put it in `.env`, never in git).
2. **Render**: sign up (GitHub login is easiest), then Account settings → API keys → create a key.
3. **GitHub**: create an **empty public** repo named `kabaad-line` and send me the URL.

## Decisions
- **D-1 (~10:28) Routing baseline made fair.** Before: the baseline was 1 vehicle doing a nearest-neighbour round of every bin, ignoring load; the plan was 3 capacity-limited vehicles. Optimised km came out *higher*, so 0% saved. Now both sides use the same fleet, the same OR-Tools solver, tomorrow's forecast loads and up to 3 depot trips per collector (`TRIPS_PER_COLLECTOR`). The only difference is that the baseline empties every bin daily (status quo) while the plan visits only bins that need it. Result on seed data: 15.6 km → 12.1 km (**22.5% saved**), 11% in move-out mode. Defensible in Q&A.
- **D-2 (~10:30) Multi-trip routing + workload balance.** Each collector gets up to 3 trips (unload at depot between trips), so bins are no longer dropped for capacity. Repeat trips carry a fixed solver penalty, so work spreads across collectors before anyone does a second trip. The penalty doesn't count toward reported km. Hindi briefing mentions the number of trips when there's more than one.
- **D-3** Python 3.13 locally (`.python-version` says 3.12, and Render uses 3.12.7 from `render.yaml`). All deps install fine on both.

- **D-4 (~10:33) Coordinates from OpenStreetMap (Overpass).** 12 of 13 hostels have their own OSM footprint. Azad Bhawan isn't mapped, so its pin uses the "Azad Bhawan Stationery" node next to it. There's no MRF/estate yard on OSM, so the depot sits near the Main Gate service area (approx). Added **Vigyan Kunj** and **Cautley-Ganga Mess**. "Faculty Residences A" → **Saraswati Kunj** (a real mapped area). Main Building = James Thomason Building; LHC = New LHC; Sports Complex = Major Dhyan Chand Stadium. Matching check: "raj" → asks Rajendra/Rajiv/Ravindra (good to show in the demo), "ganga mess" → mess.
- **D-5 (~10:37) Sourced factors, conservative throughout.** CO₂e: EPA WARM v16 recycling factors, read straight from the PDF exhibits. Metal is credited at the steel-can rate, not aluminium. E-waste/organic/MLP get no CO₂ credit. ₹/kg: TheKabadiwala Delhi doorstep list, which is what households get paid, so it understates what collectors earn. Glass ₹1 is our estimate. Vehicle fuel use and bin density are labelled *assumptions* in the README. Effect: dashboard ₹ and CO₂ figures change; see log for the new values.
- **D-6 (~10:40) Real per-step plan progress.** New `PlanRun.steps` column, `POST /internal/plan-runs/{id}/step`. Both the local thread and the Render Workflow (`plan_tomorrow`) report each step as it finishes. The dashboard shows 6 chips lighting up (Load state → Forecast → Select stops → Solve VRP → Publish → Hindi TTS × collectors) plus an **engine: Render Workflow / local fallback** badge. That makes the Render track visible on screen. Progress callbacks never fail a run.
- **D-7 (~10:45) Inline voice panel instead of the floating widget.** The `<elevenlabs-convai>` embed renders as a corner bubble, so the voice box sat empty. Switched to the official `@elevenlabs/react` SDK (`ConversationProvider` + `useConversation`, WebRTC). It gives a big mic button with ripple, Hindi status text (सुन रहे हैं… / एजेंट बोल रहा है…), a **live transcript** of the call, and a "✓ Bin status logged → dashboard" receipt chip on every server tool call. `collector_name` is passed as a dynamic variable. Voice is now visibly the core.
- **D-8 (~10:45) Briefings in Devanagari.** TTS now reads "राजेंद्र भवन", not "Rajendra Bhawan". The name comes from the longest Devanagari alias (`hindi_name()`), and fuller aliases were added where missing.
- **D-9 (~10:50) Weekday-aware forecast.** Rises are bucketed by weekend/weekday and the matching rate is used when there's ≥24 h of such data. Tomorrow (25 Oct) is a Sunday: Rajendra Bhawan's rate is 46.7%/day (weekend) vs 35.9% (weekday). Forecasts ≥100% show as "forecast: overflowing" rather than "170%".
- **D-10 (~10:55) UI fixes from headless screenshots** (Playwright, desktop + 375px): the display font had no Devanagari glyphs, so Hind was added to its stack; the material chart is now horizontal (labels overlapped on mobile); stat cards go 1-column under 420px; responsive map height. Emoji show as boxes in headless Chromium only, which is fine on real devices.

## Log
- 10:21 Start. Repo had never been run: no venv, no node_modules, not a git repo, no `gh`/`ngrok`.
- 10:24 Backend up. All 3 voice tools verified with Devanagari/Hinglish input (`राजेंद्र भवन के पीछे वाला बिन` → Rajendra Bhawan, "ubal raha hai" → 110% overflow). Pickup + local plan run work.
- 10:30 Routing fix (D-1, D-2). Frontend builds clean. Committed.
- 10:33 OSM coordinates in, DB reseeded, routing re-checked: 10.2 → 7.9 km (22.9% saved), all 3 collectors get work.
- 10:37 Sourced numbers + README Sources table.
- 10:55 A4/A5 done and screenshotted at desktop + mobile. Ready for ElevenLabs keys.
