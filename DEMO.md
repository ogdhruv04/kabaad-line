# Demo video script (target 2:30, hard max 3:00)

**Before recording:**
- Start the backend, the frontend and the tunnel, and run the `--update` line from the README. Test one voice report before recording.
- Use headphones, so the agent's voice doesn't loop back into the mic.
- Run `python -m server.seed` *only if* you want a clean feed (it wipes voice logs). Otherwise leave it as is.

| # | Time | Screen | Say (rough) |
|---|---|---|---|
| 1 | 0:00–0:15 | Dashboard, map visible | "Campus waste is moved by safai staff and kabadiwalas who mostly don't use apps. Kabaad Line lets them run it **by voice, in Hindi**." |
| 2 | 0:15–0:55 | **Collector** tab, tap the mic as Ramesh | Speak: **"राजेंद्र भवन के पीछे वाला डस्टबिन भर गया है"**. The live transcript appears, then the "✓ Bin status logged → dashboard" chip. Then say **"Cautley se baarah kilo gatta uthaya"**: the agent replies with the ₹ value and today's total. Optional: say "Raj bhawan…" and the agent asks "Rajendra ya Rajiv?" |
| 3 | 0:55–1:05 | "What the agent logged" feed flashes | "No typing, no reading. What he said is already on the supervisor's dashboard." |
| 4 | 1:05–1:20 | **Request pickup** tab (switch to हिंदी), submit 8 kg PET at Govind Bhawan | "Students add scrap pickups, especially at semester move-out." |
| 5 | 1:20–1:50 | Dashboard → **Plan tomorrow**. The six step chips light up as each stage finishes. | "The planner forecasts fill (weekday-aware), picks only bins that need a visit, solves a capacitated VRP with OR-Tools, and generates a Hindi audio briefing for each collector." |
| 6 | 1:50–2:10 | Back to the Dashboard: routes on the map, then **Route km saved %** and the Impact card | "Same crew, same trucks, same solver, but we only visit bins that need it: about 20% fewer km than the fixed every-bin round. The overflow Ramesh just reported is the first stop." |
| 7 | 2:10–2:25 | Collector tab → press play on **Ramesh's Hindi audio briefing** | Let ~5 s of audio play. |
| 8 | 2:25–2:40 | Impact card (point at the Simulated badges) | "Recyclables diverted, ₹ to collectors, CO₂e from EPA WARM factors. History is simulated and labelled so; voice, routing, planning runs and audio are real. Built with ElevenLabs." |

**Backup lines if the agent mishears:** "Govind Bhawan ka dibba poora bhara hai" · "paanch kilo bottle uthaya".
