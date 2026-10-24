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
    drops (those are collections). Weekday-aware: if tomorrow is a weekend (or weekday), use the rate
    seen on matching days when there's at least a day of such data — hostels fill faster on weekends.
    """
    out = {}
    multiplier = config.MOVE_OUT_MULTIPLIER if state.get("move_out") else 1.0
    weekend_tomorrow = datetime.fromisoformat(state["plan_date"]).weekday() >= 5
    for b in state["bins"]:
        readings = sorted(b.get("readings", []))
        if not readings:
            out[str(b["id"])] = {"current": 0, "rate_per_day": 0, "predicted": 0, "basis": "no data"}
            continue
        rises = {True: 0.0, False: 0.0}  # keyed by "is weekend"
        hours = {True: 0.0, False: 0.0}
        for (t0, f0), (t1, f1) in zip(readings, readings[1:]):
            dt = (datetime.fromisoformat(t1) - datetime.fromisoformat(t0)).total_seconds() / 3600
            if f1 >= f0 and dt > 0:
                wk = datetime.fromisoformat(t1).weekday() >= 5
                rises[wk] += f1 - f0
                hours[wk] += dt
        if hours[weekend_tomorrow] >= 24:
            rate = rises[weekend_tomorrow] / hours[weekend_tomorrow] * 24
            basis = "weekend rate" if weekend_tomorrow else "weekday rate"
        else:
            total_h = hours[True] + hours[False]
            rate = (rises[True] + rises[False]) / total_h * 24 if total_h else 0
            basis = "7-day rate"
        current = readings[-1][1]
        predicted = current + rate * multiplier
        out[str(b["id"])] = {"current": round(current, 1), "rate_per_day": round(rate, 1), "predicted": round(predicted, 1), "basis": basis}
    return out


# ---------------------------------------------------------------- step 2: choose stops
def select_stops(state: dict, forecast: dict) -> list[dict]:
    stops: dict[int, dict] = {}

    def stop_for(b):
        return stops.setdefault(b["id"], {"location_id": b["id"], "name": b["name"], "name_hi": b.get("name_hi") or b["name"],
                                          "lat": b["lat"], "lng": b["lng"], "est_kg": 0.0, "reasons": []})

    by_id = {b["id"]: b for b in state["bins"]}
    for b in state["bins"]:
        f = forecast.get(str(b["id"]), {})
        pred = f.get("predicted", 0)
        if pred >= config.FILL_THRESHOLD:
            s = stop_for(b)
            s["est_kg"] += b["capacity_l"] * min(pred, 120) / 100 * config.KG_PER_LITRE
            s["reasons"].append(f"forecast {pred:.0f}%" if pred < 100 else "forecast: overflowing")
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
    """Multi-trip capacitated VRP with OR-Tools, balanced so no collector's shift is much longer than another's."""
    solved = _vrp(state, stops, time_limit_s)
    solved["baseline_km"] = baseline_km(state)
    return solved


def _vrp(state: dict, stops: list[dict], time_limit_s: int) -> dict:
    """One vehicle per collector. Optional "reload" nodes at the depot let a vehicle unload and go again
    (OR-Tools' reload pattern: negative demand + capacity slack). A Time dimension (drive + load + unload)
    with a global span cost keeps shifts even across collectors."""
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    collectors = state["collectors"]
    depot = state["depot"]
    if not stops:
        return {"routes": [], "optimized_km": 0.0, "dropped": []}

    n_veh = len(collectors)
    caps = [int(c["vehicle_capacity_kg"]) for c in collectors]
    max_cap = max(caps)
    n_reload = n_veh * (config.TRIPS_PER_COLLECTOR - 1)
    depot_ll = (depot["lat"], depot["lng"])
    # node 0 = depot, 1..n_reload = depot copies for unloading, then the stops
    coords = [depot_ll] * (1 + n_reload) + [(s["lat"], s["lng"]) for s in stops]
    first_stop = 1 + n_reload
    dist = [[int(road_km(a, b) * 1000) for b in coords] for a in coords]
    demands = [0] + [-max_cap] * n_reload + [max(1, int(round(s["est_kg"]))) for s in stops]

    def service_min(node: int) -> float:
        if node == 0:
            return 0
        if node < first_stop:
            return config.UNLOAD_MIN
        return config.STOP_MIN + demands[node] / 100 * config.LOAD_MIN_PER_100KG

    travel_min = [[d / 1000 / config.CART_KMPH * 60 for d in row] for row in dist]
    time_m = [[int(round(service_min(i) + travel_min[i][j])) for j in range(len(coords))] for i in range(len(coords))]

    manager = pywrapcp.RoutingIndexManager(len(coords), n_veh, 0)
    routing = pywrapcp.RoutingModel(manager)

    dist_idx = routing.RegisterTransitCallback(lambda i, j: dist[manager.IndexToNode(i)][manager.IndexToNode(j)])
    routing.SetArcCostEvaluatorOfAllVehicles(dist_idx)

    demand_idx = routing.RegisterUnaryTransitCallback(lambda i: demands[manager.IndexToNode(i)])
    routing.AddDimensionWithVehicleCapacity(demand_idx, max_cap, caps, True, "Capacity")  # slack absorbs unloading
    capacity = routing.GetDimensionOrDie("Capacity")

    time_idx = routing.RegisterTransitCallback(lambda i, j: time_m[manager.IndexToNode(i)][manager.IndexToNode(j)])
    routing.AddDimension(time_idx, 0, 24 * 60, True, "Time")
    routing.GetDimensionOrDie("Time").SetGlobalSpanCostCoefficient(config.BALANCE_M_PER_MIN)

    for node in range(1, first_stop):  # unloading trips are free to skip
        routing.AddDisjunction([manager.NodeToIndex(node)], 0)
    for node in range(first_stop, len(coords)):  # drop a stop only if capacity makes it impossible
        capacity.SlackVar(manager.NodeToIndex(node)).SetValue(0)
        routing.AddDisjunction([manager.NodeToIndex(node)], 10_000_000)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = time_limit_s
    solution = routing.SolveWithParameters(params)

    routes, visited = [], set()
    if solution:
        for v, c in enumerate(collectors):
            idx = routing.Start(v)
            ordered, meters, minutes, trip, prev = [], 0, 0, 1, 0
            while not routing.IsEnd(idx):
                nxt = solution.Value(routing.NextVar(idx))
                node, nnode = manager.IndexToNode(idx), manager.IndexToNode(nxt)
                if node >= first_stop:
                    ordered.append({**stops[node - first_stop], "trip": trip})
                    visited.add(node)
                elif node != 0 and ordered and ordered[-1]["trip"] == trip:  # unloaded after some stops
                    trip += 1
                meters += dist[node][nnode]
                minutes += time_m[node][nnode]
                idx = nxt
            if ordered:
                routes.append({"collector_id": c["id"], "collector_name": c["name"], "stops": ordered,
                               "trips": ordered[-1]["trip"], "distance_km": round(meters / 1000, 2),
                               "shift_min": minutes, "load_kg": round(sum(s["est_kg"] for s in ordered), 1)})
    dropped = [stops[n - first_stop]["name"] for n in range(first_stop, len(coords)) if n not in visited]
    optimized = round(sum(r["distance_km"] for r in routes), 2)
    return {"routes": routes, "optimized_km": optimized, "dropped": dropped}


# ---------------------------------------------------------------- step 4: briefing script
def briefing_text(route: dict, plan_date: str) -> str:
    """Hindi morning briefing, read out by ElevenLabs TTS. Keep sentences short — it's heard, not read."""
    stops = route["stops"]
    names = [s.get("name_hi") or s["name"] for s in stops]  # Devanagari so the Hindi voice pronounces them naturally
    lines = [f"नमस्ते {route['collector_name']} जी। कल के लिए आपका रूट तैयार है।",
             f"कुल {len(stops)} स्टॉप हैं, लगभग {route['distance_km']:.1f} किलोमीटर, और करीब {route['load_kg']:.0f} किलो कचरा।"]
    if route.get("shift_min"):
        lines.append(f"अंदाज़न {route['shift_min']} मिनट का काम है।")
    if route.get("trips", 1) > 1:
        lines.append(f"गाड़ी भरने पर डिपो खाली करके आइए, कुल {route['trips']} चक्कर लगेंगे।")
    if names:
        lines.append(f"पहला स्टॉप {names[0]} है।")
        if len(names) > 1:
            lines.append("उसके बाद " + ", फिर ".join(names[1:]) + "।")
    pickups = [s for s in stops if any(r.startswith("pickup") for r in s["reasons"])]
    if pickups:
        lines.append(f"{len(pickups)} जगह पर छात्रों ने कबाड़ उठाने के लिए बुलाया है: " + ", ".join(p.get("name_hi") or p["name"] for p in pickups) + "।")
    overflow = [s for s in stops if any("overflow" in r for r in s["reasons"])]
    if overflow:
        lines.append("ये डिब्बे भरे हुए बताए गए हैं, पहले इन्हें देखिए: " + ", ".join(o.get("name_hi") or o["name"] for o in overflow) + "।")
    lines.append("गत्ता, बोतल और पन्नी अलग-अलग रखिए। काम पूरा हो तो बोलकर बता दीजिए कितना किलो उठाया। धन्यवाद।")
    return " ".join(lines)


# ---------------------------------------------------------------- whole pipeline (local fallback)
PIPELINE_STEPS = ["load_state", "forecast_fill", "select_stops", "solve_routes", "publish_routes", "synthesize_briefing"]


def run_pipeline(state: dict, on_step=lambda step: None) -> dict:
    forecast = forecast_fill(state)
    on_step("forecast_fill")
    stops = select_stops(state, forecast)
    on_step("select_stops")
    solved = solve_routes(state, stops)
    for r in solved["routes"]:
        r["briefing_text"] = briefing_text(r, state["plan_date"])
    on_step("solve_routes")
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
