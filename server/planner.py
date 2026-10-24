"""Pure planning functions. Inputs and outputs are plain JSON-able dicts so the same code runs:
  - inside Render Workflow tasks (server/workflows.py), each step on its own container, and
  - in-process as a fallback (POST /api/plan/run when Render isn't configured).

state = {
  "plan_date": "2026-10-25",
  "move_out": False,
  "depot": {"id", "name", "lat", "lng"},
  "bins": [{"id", "name", "kind", "lat", "lng", "capacity_l", "readings": [[iso_ts, fill_pct], ...]}],
  "overflow_location_ids": [ids reported overflowing in the last 24h],
  "pickups": [{"id", "location_id", "material", "est_kg"}],
  "collectors": [{"id", "name", "vehicle_capacity_kg"}],
}
"""
from __future__ import annotations

import math
from datetime import datetime

from . import config


# ---------------------------------------------------------------- geometry
def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def road_km(a, b) -> float:
    return haversine_km(a, b) * config.ROAD_FACTOR


def tour_km(points: list[tuple[float, float]]) -> float:
    return sum(road_km(points[i], points[i + 1]) for i in range(len(points) - 1))


# ---------------------------------------------------------------- step 1: forecast
def forecast_fill(state: dict) -> dict:
    """Predict tomorrow-morning fill % per bin from its recent fill rate.

    Simple and explainable on purpose: rate = average rise per day over the last 7 days, ignoring
    drops (those are collections). Swap in a weekday-aware model if you have time.
    """
    out = {}
    multiplier = config.MOVE_OUT_MULTIPLIER if state.get("move_out") else 1.0
    for b in state["bins"]:
        readings = sorted(b.get("readings", []))
        if not readings:
            out[str(b["id"])] = {"current": 0, "rate_per_day": 0, "predicted": 0}
            continue
        rises, hours = 0.0, 0.0
        for (t0, f0), (t1, f1) in zip(readings, readings[1:]):
            dt = (datetime.fromisoformat(t1) - datetime.fromisoformat(t0)).total_seconds() / 3600
            if f1 >= f0 and dt > 0:
                rises += f1 - f0
                hours += dt
        rate = (rises / hours * 24) if hours else 0
        current = readings[-1][1]
        predicted = current + rate * multiplier
        out[str(b["id"])] = {"current": round(current, 1), "rate_per_day": round(rate, 1), "predicted": round(predicted, 1)}
    return out


# ---------------------------------------------------------------- step 2: choose stops
def select_stops(state: dict, forecast: dict) -> list[dict]:
    stops: dict[int, dict] = {}

    def stop_for(b):
        return stops.setdefault(b["id"], {"location_id": b["id"], "name": b["name"], "lat": b["lat"], "lng": b["lng"],
                                          "est_kg": 0.0, "reasons": []})

    by_id = {b["id"]: b for b in state["bins"]}
    for b in state["bins"]:
        f = forecast.get(str(b["id"]), {})
        pred = f.get("predicted", 0)
        if pred >= config.FILL_THRESHOLD:
            s = stop_for(b)
            s["est_kg"] += b["capacity_l"] * min(pred, 120) / 100 * config.KG_PER_LITRE
            s["reasons"].append(f"forecast {pred:.0f}%")
    for loc_id in state.get("overflow_location_ids", []):
        if loc_id in by_id:
            s = stop_for(by_id[loc_id])
            if not any(r.startswith("forecast") for r in s["reasons"]):
                s["est_kg"] += by_id[loc_id]["capacity_l"] * config.KG_PER_LITRE
            s["reasons"].append("overflow reported by voice")
    for p in state.get("pickups", []):
        if p["location_id"] in by_id:
            s = stop_for(by_id[p["location_id"]])
            s["est_kg"] += p["est_kg"]
            s["reasons"].append(f"pickup: {p['material']} ~{p['est_kg']:.0f}kg")
    for s in stops.values():
        s["est_kg"] = round(s["est_kg"], 1)
    return list(stops.values())


# ---------------------------------------------------------------- step 3: routes
def baseline_km(state: dict) -> float:
    """Status quo: the same collectors run a fixed daily round that empties EVERY bin, routed by the same solver.

    Same fleet, same trip limit, same forecast loads and same optimiser on both sides, so the saving comes only
    from skipping bins that don't need a visit yet.
    """
    forecast = forecast_fill(state)
    every_bin = [{"location_id": b["id"], "name": b["name"], "lat": b["lat"], "lng": b["lng"], "reasons": [],
                  "est_kg": b["capacity_l"] * min(forecast.get(str(b["id"]), {}).get("predicted", 0), 120) / 100 * config.KG_PER_LITRE}
                 for b in state["bins"]]
    return _vrp(state, every_bin, time_limit_s=2)["optimized_km"]


def solve_routes(state: dict, stops: list[dict], time_limit_s: int = 3) -> dict:
    """Capacitated VRP with OR-Tools: each collector may do up to TRIPS_PER_COLLECTOR depot round trips."""
    solved = _vrp(state, stops, time_limit_s)
    solved["baseline_km"] = baseline_km(state)
    return solved


def _vrp(state: dict, stops: list[dict], time_limit_s: int) -> dict:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    collectors = state["collectors"]
    depot = state["depot"]
    if not stops:
        return {"routes": [], "optimized_km": 0.0, "dropped": []}

    # One OR-Tools vehicle per (collector, trip): unloading at the depot between trips resets capacity.
    trips = [c for _ in range(config.TRIPS_PER_COLLECTOR) for c in collectors]
    nodes = [(depot["lat"], depot["lng"])] + [(s["lat"], s["lng"]) for s in stops]
    dist = [[int(road_km(a, b) * 1000) for b in nodes] for a in nodes]
    demands = [0] + [max(1, int(round(s["est_kg"]))) for s in stops]
    caps = [int(c["vehicle_capacity_kg"]) for c in trips]

    manager = pywrapcp.RoutingIndexManager(len(nodes), len(trips), 0)
    routing = pywrapcp.RoutingModel(manager)

    def dist_cb(i, j):
        return dist[manager.IndexToNode(i)][manager.IndexToNode(j)]

    transit = routing.RegisterTransitCallback(dist_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit)
    for v in range(len(collectors), len(trips)):  # repeat trips cost extra, so work spreads across collectors first
        routing.SetFixedCostOfVehicle(5000, v)

    def demand_cb(i):
        return demands[manager.IndexToNode(i)]

    demand_idx = routing.RegisterUnaryTransitCallback(demand_cb)
    routing.AddDimensionWithVehicleCapacity(demand_idx, 0, caps, True, "Capacity")
    for node in range(1, len(nodes)):  # allow dropping a stop only if capacity makes it impossible
        routing.AddDisjunction([manager.NodeToIndex(node)], 10_000_000)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = time_limit_s
    solution = routing.SolveWithParameters(params)

    by_collector: dict[int, dict] = {}
    visited = set()
    if solution:
        for v, c in enumerate(trips):
            idx = routing.Start(v)
            ordered, meters = [], 0
            while not routing.IsEnd(idx):
                node = manager.IndexToNode(idx)
                if node != 0:
                    ordered.append(stops[node - 1])
                    visited.add(node)
                nxt = solution.Value(routing.NextVar(idx))
                meters += dist[node][manager.IndexToNode(nxt)]
                idx = nxt
            if ordered:
                r = by_collector.setdefault(c["id"], {"collector_id": c["id"], "collector_name": c["name"], "stops": [],
                                                      "trips": 0, "distance_km": 0.0, "load_kg": 0.0})
                r["trips"] += 1
                r["stops"] += [{**s, "trip": r["trips"]} for s in ordered]
                r["distance_km"] = round(r["distance_km"] + meters / 1000, 2)
                r["load_kg"] = round(r["load_kg"] + sum(s["est_kg"] for s in ordered), 1)
    routes = list(by_collector.values())
    dropped = [stops[n - 1]["name"] for n in range(1, len(nodes)) if n not in visited]
    optimized = round(sum(r["distance_km"] for r in routes), 2)
    return {"routes": routes, "optimized_km": optimized, "dropped": dropped}


# ---------------------------------------------------------------- step 4: briefing script
def briefing_text(route: dict, plan_date: str) -> str:
    """Hindi morning briefing, read out by ElevenLabs TTS. Keep sentences short — it's heard, not read."""
    stops = route["stops"]
    names = [s["name"] for s in stops]
    lines = [f"नमस्ते {route['collector_name']} जी। कल के लिए आपका रूट तैयार है।",
             f"कुल {len(stops)} स्टॉप हैं, लगभग {route['distance_km']:.1f} किलोमीटर, और करीब {route['load_kg']:.0f} किलो कचरा।"]
    if route.get("trips", 1) > 1:
        lines.append(f"गाड़ी भरने पर डिपो खाली करके आइए, कुल {route['trips']} चक्कर लगेंगे।")
    if names:
        lines.append(f"पहला स्टॉप {names[0]} है।")
        if len(names) > 1:
            lines.append("उसके बाद " + ", फिर ".join(names[1:]) + "।")
    pickups = [s for s in stops if any(r.startswith("pickup") for r in s["reasons"])]
    if pickups:
        lines.append(f"{len(pickups)} जगह पर छात्रों ने कबाड़ उठाने के लिए बुलाया है: " + ", ".join(p["name"] for p in pickups) + "।")
    overflow = [s for s in stops if any("overflow" in r for r in s["reasons"])]
    if overflow:
        lines.append("ये डिब्बे भरे हुए बताए गए हैं, पहले इन्हें देखिए: " + ", ".join(o["name"] for o in overflow) + "।")
    lines.append("गत्ता, बोतल और पन्नी अलग-अलग रखिए। काम पूरा हो तो बोलकर बता दीजिए कितना किलो उठाया। धन्यवाद।")
    return " ".join(lines)


# ---------------------------------------------------------------- whole pipeline (local fallback)
def run_pipeline(state: dict) -> dict:
    forecast = forecast_fill(state)
    stops = select_stops(state, forecast)
    solved = solve_routes(state, stops)
    for r in solved["routes"]:
        r["briefing_text"] = briefing_text(r, state["plan_date"])
    solved["forecast"] = forecast
    return solved


def impact_summary(solved: dict) -> dict:
    saved_km = max(0.0, solved["baseline_km"] - solved["optimized_km"])
    fuel_l = saved_km * config.DIESEL_L_PER_KM
    return {
        "baseline_km": solved["baseline_km"],
        "optimized_km": solved["optimized_km"],
        "km_saved": round(saved_km, 2),
        "pct_saved": round(100 * saved_km / solved["baseline_km"], 1) if solved["baseline_km"] else 0,
        "fuel_l_saved": round(fuel_l, 2),
        "co2_kg_saved": round(fuel_l * config.CO2_KG_PER_L_DIESEL, 2),
        "stops": sum(len(r["stops"]) for r in solved["routes"]),
        "dropped": solved.get("dropped", []),
    }
