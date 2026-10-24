"""Render Workflows: the nightly planning pipeline as durable, retryable tasks.

SDK notes (render==1.4, verified against the installed package):
  - The package is `render` (the old `render_sdk` is a deprecated shim).
  - Every task takes a TaskContext as its FIRST parameter.
  - `await ctx.run(other_task, *args)` runs a subtask on its own container and returns its result.
  - Args/results must be JSON-serialisable — which is why planner.py works on plain dicts.
  - Start command on Render:  render-workflows server.workflows:app
  - The backend triggers it with Render().workflows.start_task("<workflow-service-slug>/plan_tomorrow", {...}).

Pipeline (each box is its own task run, visible in the Render dashboard):

  plan_tomorrow
    ├─ load_state            GET  backend /internal/state
    ├─ forecast_fill         pure python
    ├─ select_stops          pure python
    ├─ solve_routes          OR-Tools CVRP (heavier plan)
    ├─ publish_routes        POST backend /internal/plan-runs/{id}/result
    └─ synthesize_briefing   ElevenLabs TTS, one run PER COLLECTOR IN PARALLEL
"""
from __future__ import annotations

import asyncio
import base64

import httpx
from render import Retry, TaskContext, Workflows

from . import config, planner, tts

app = Workflows(default_retry=Retry(max_retries=3, wait_duration_ms=2000, backoff_scaling=2.0), default_timeout=300)

HEADERS = {"X-Tool-Secret": config.TOOL_SHARED_SECRET}


def _backend(method: str, path: str, **kw):
    r = httpx.request(method, f"{config.BACKEND_URL}{path}", headers=HEADERS, timeout=60, **kw)
    r.raise_for_status()
    return r.json()


@app.task
def load_state(ctx: TaskContext, plan_date: str, move_out: bool) -> dict:
    return _backend("GET", "/internal/state", params={"plan_date": plan_date, "move_out": str(move_out).lower()})


@app.task
def forecast_fill(ctx: TaskContext, state: dict) -> dict:
    return planner.forecast_fill(state)


@app.task
def select_stops(ctx: TaskContext, state: dict, forecast: dict) -> list:
    return planner.select_stops(state, forecast)


@app.task(timeout_seconds=120)
def solve_routes(ctx: TaskContext, state: dict, stops: list) -> dict:
    solved = planner.solve_routes(state, stops, time_limit_s=10)  # more search time than the local fallback
    for r in solved["routes"]:
        r["briefing_text"] = planner.briefing_text(r, state["plan_date"])
    return solved


@app.task
def publish_routes(ctx: TaskContext, plan_run_id: int, solved: dict) -> list:
    return _backend("POST", f"/internal/plan-runs/{plan_run_id}/result", json=solved)["routes"]


@app.task(retry=Retry(max_retries=5, wait_duration_ms=3000, backoff_scaling=2.0))
def synthesize_briefing(ctx: TaskContext, route_id: int, text: str) -> dict:
    mp3 = tts.synthesize(text)
    if not mp3:
        return {"route_id": route_id, "audio": False, "reason": "ElevenLabs not configured"}
    _backend("POST", f"/internal/routes/{route_id}/audio", json={"mp3_b64": base64.b64encode(mp3).decode()})
    return {"route_id": route_id, "audio": True, "bytes": len(mp3)}


@app.task(timeout_seconds=900)
async def plan_tomorrow(ctx: TaskContext, plan_run_id: int, plan_date: str, move_out: bool = False) -> dict:
    def step(name: str) -> None:  # progress for the dashboard; never fail the run over it
        try:
            _backend("POST", f"/internal/plan-runs/{plan_run_id}/step", json={"step": name})
        except httpx.HTTPError:
            pass

    try:
        state = await ctx.run(load_state, plan_date, move_out)
        step("load_state")
        forecast = await ctx.run(forecast_fill, state)
        step("forecast_fill")
        stops = await ctx.run(select_stops, state, forecast)
        step("select_stops")
        solved = await ctx.run(solve_routes, state, stops)
        step("solve_routes")
        solved["forecast"] = forecast
        routes = await ctx.run(publish_routes, plan_run_id, solved)
        step("publish_routes")
        # Fan out: one TTS task per collector, in parallel, each with its own retries.
        audio = await asyncio.gather(*[ctx.run(synthesize_briefing, r["route_id"], r["briefing_text"]) for r in routes])
        step("synthesize_briefing")
        _backend("POST", f"/internal/plan-runs/{plan_run_id}/status", json={"status": "done"})
        return {"plan_run_id": plan_run_id, "impact": planner.impact_summary(solved), "audio": audio}
    except Exception as e:
        _backend("POST", f"/internal/plan-runs/{plan_run_id}/status", json={"status": "failed", "error": str(e)[:500]})
        raise


if __name__ == "__main__":
    app.start()
