"""Kabaad Line API.

  /api/*       public JSON for the web app
  /tools/*     ElevenLabs Agent server tools (header X-Tool-Secret)
  /internal/*  called back by Render Workflow tasks (header X-Tool-Secret)

Run locally:  uvicorn server.main:app --reload
"""
from __future__ import annotations

import base64
import hashlib
import re
import threading
import time
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config, planner, tts
from .db import Base, SessionLocal, engine, get_db
from .matching import match_location
from .models import AudioClip, BinReading, Collection, Collector, Location, PickupRequest, PlanRun, Report, Route

app = FastAPI(title="Kabaad Line")
IST = timezone(timedelta(hours=5, minutes=30))
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(func.count(Location.id))) == 0:
            from .seed import seed
            seed()
    if config.AUTO_PLAN_AT_IST:
        threading.Thread(target=nightly_planner, daemon=True).start()


def nightly_planner() -> None:
    """Plan tomorrow automatically every evening (same pipeline as the button); collectors get briefings overnight."""
    hh, mm = map(int, config.AUTO_PLAN_AT_IST.split(":"))
    while True:
        now = datetime.now(IST)
        at = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        time.sleep(((at if at > now else at + timedelta(days=1)) - now).total_seconds())
        try:
            with SessionLocal() as db:
                start_plan(db, None, move_out=False)
        except Exception as e:  # never kill the scheduler
            print("nightly plan failed:", e)


def require_secret(x_tool_secret: str = Header(default="")) -> None:
    if x_tool_secret != config.TOOL_SHARED_SECRET:
        raise HTTPException(401, "bad X-Tool-Secret")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(ts: datetime) -> datetime:  # SQLite drops tzinfo
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def latest_fill(db: Session) -> dict[int, BinReading]:
    sub = select(BinReading.location_id, func.max(BinReading.id).label("mid")).group_by(BinReading.location_id).subquery()
    rows = db.scalars(select(BinReading).join(sub, BinReading.id == sub.c.mid)).all()
    return {r.location_id: r for r in rows}


# ======================================================================= public API
@app.get("/api/health")
def health():
    return {"ok": True, "workflow_configured": bool(config.RENDER_API_KEY and config.WORKFLOW_SLUG), "auto_plan_at_ist": config.AUTO_PLAN_AT_IST,
            "tts_configured": bool(config.ELEVENLABS_API_KEY and config.ELEVENLABS_VOICE_ID)}


@app.get("/api/locations")
def locations(db: Session = Depends(get_db)):
    fills = latest_fill(db)
    out = []
    for l in db.scalars(select(Location)).all():
        r = fills.get(l.id)
        out.append({"id": l.id, "name": l.name, "kind": l.kind, "lat": l.lat, "lng": l.lng, "capacity_l": l.capacity_l,
                    "fill_pct": r.fill_pct if r else None, "fill_source": r.source if r else None,
                    "fill_ts": aware(r.ts).isoformat() if r else None})
    return out


@app.get("/api/collectors")
def collectors(db: Session = Depends(get_db)):
    return [{"id": c.id, "name": c.name, "vehicle_capacity_kg": c.vehicle_capacity_kg} for c in db.scalars(select(Collector))]


@app.get("/api/materials")
def materials():
    return config.MATERIALS


@app.get("/api/kpis")
def kpis(days: int = 7, db: Session = Depends(get_db)):
    since = utcnow() - timedelta(days=days)
    rows = db.execute(select(Collection.material, Collection.simulated, func.sum(Collection.kg))
                      .where(Collection.ts >= since).group_by(Collection.material, Collection.simulated)).all()
    by_mat: dict[str, dict] = {}
    for mat, sim, kg in rows:
        d = by_mat.setdefault(mat, {"material": mat, "label": config.MATERIALS.get(mat, {}).get("label", mat), "kg": 0, "kg_real": 0})
        d["kg"] += kg or 0
        if not sim:
            d["kg_real"] += kg or 0
    total = sum(d["kg"] for d in by_mat.values())
    recyclable = sum(d["kg"] for m, d in by_mat.items() if config.MATERIALS.get(m, {}).get("rate_inr_per_kg", 0) > 0)
    inr = sum(d["kg"] * config.MATERIALS.get(m, {}).get("rate_inr_per_kg", 0) for m, d in by_mat.items())
    co2 = sum(d["kg"] * config.MATERIALS.get(m, {}).get("co2e_avoided_per_kg", 0) for m, d in by_mat.items())
    mlp = by_mat.get("mlp", {}).get("kg", 0)
    last_run = db.scalars(select(PlanRun).where(PlanRun.status == "done").order_by(PlanRun.id.desc())).first()
    fills = latest_fill(db)
    return {
        "days": days,
        "total_kg": round(total, 1),
        "recyclable_kg": round(recyclable, 1),
        "diversion_pct": round(100 * recyclable / total, 1) if total else 0,
        "inr_recovered": round(inr),
        "co2e_avoided_kg": round(co2, 1),
        "mlp_share_pct": round(100 * mlp / total, 1) if total else 0,
        "by_material": sorted(by_mat.values(), key=lambda d: -d["kg"]),
        "bins_over_80": sum(1 for r in fills.values() if r.fill_pct >= 80),
        "open_pickups": db.scalar(select(func.count(PickupRequest.id)).where(PickupRequest.status == "pending")),
        "voice_reports_24h": db.scalar(select(func.count(Report.id)).where(Report.simulated.is_(False), Report.ts >= utcnow() - timedelta(hours=24))),
        "routing": (last_run.summary or {}).get("impact") if last_run else None,
        "simulated_note": "Collection history and sensor fill levels before today are simulated.",
    }


@app.get("/api/feed")
def feed(limit: int = 30, db: Session = Depends(get_db)):
    names = {l.id: l.name for l in db.scalars(select(Location))}
    cnames = {c.id: c.name for c in db.scalars(select(Collector))}
    items = []
    for r in db.scalars(select(Report).order_by(Report.id.desc()).limit(limit)):
        items.append({"type": "report", "kind": r.kind, "text": r.text, "location": names.get(r.location_id, "?"),
                      "who": r.reporter, "channel": r.channel, "simulated": r.simulated, "ts": aware(r.ts).isoformat()})
    for c in db.scalars(select(Collection).where(Collection.simulated.is_(False)).order_by(Collection.id.desc()).limit(limit)):
        items.append({"type": "collection", "kind": c.material, "text": f"{c.kg:g} kg {config.MATERIALS.get(c.material, {}).get('label', c.material)}",
                      "location": names.get(c.location_id, "—"), "who": cnames.get(c.collector_id, "?"), "channel": "voice",
                      "simulated": False, "ts": aware(c.ts).isoformat()})
    for p in db.scalars(select(PickupRequest).order_by(PickupRequest.id.desc()).limit(limit)):
        items.append({"type": "pickup", "kind": p.material, "text": f"Pickup request: ~{p.est_kg:g} kg {p.material}",
                      "location": names.get(p.location_id, "?"), "who": p.contact or "student", "channel": "web",
                      "simulated": False, "ts": aware(p.ts).isoformat()})
    items.sort(key=lambda i: (not i["simulated"], i["ts"]), reverse=True)
    return items[:limit]


class PickupIn(BaseModel):
    location_id: int
    material: str
    est_kg: float = Field(5, ge=0, le=1000)
    contact: str = ""
    note: str = ""


@app.post("/api/pickups")
def create_pickup(body: PickupIn, db: Session = Depends(get_db)):
    if not db.get(Location, body.location_id):
        raise HTTPException(404, "unknown location")
    p = PickupRequest(location_id=body.location_id, material=config.normalize_material(body.material),
                      est_kg=body.est_kg, contact=body.contact, note=body.note)
    db.add(p)
    db.commit()
    return {"id": p.id, "status": p.status}


@app.get("/api/pickups")
def list_pickups(limit: int = 8, db: Session = Depends(get_db)):
    names = {l.id: l.name for l in db.scalars(select(Location))}
    return [{"id": p.id, "location": names.get(p.location_id, "?"), "material": p.material, "est_kg": p.est_kg,
             "status": p.status, "ts": aware(p.ts).isoformat()}
            for p in db.scalars(select(PickupRequest).order_by(PickupRequest.id.desc()).limit(limit))]


class WebReportIn(BaseModel):
    location_id: int
    kind: str = "overflow"
    text: str = ""


@app.post("/api/reports")
def create_report(body: WebReportIn, db: Session = Depends(get_db)):
    db.add(Report(location_id=body.location_id, kind=body.kind, text=body.text, reporter="student", channel="web"))
    if body.kind == "overflow":
        db.add(BinReading(location_id=body.location_id, fill_pct=110, source="student"))
    db.commit()
    return {"ok": True}


# ======================================================================= planning
DEVANAGARI = re.compile(r"[\u0900-\u097F]")


def hindi_name(loc: Location) -> str:
    """Longest Devanagari alias, e.g. "राजेंद्र भवन", so TTS says the place the way collectors do."""
    hi = [a for a in (loc.aliases or []) if DEVANAGARI.search(a)]
    return max(hi, key=len) if hi else loc.name


def build_state(db: Session, plan_date: str, move_out: bool) -> dict:
    since = utcnow() - timedelta(days=7)
    locs = db.scalars(select(Location)).all()
    depot = next(l for l in locs if l.kind == "depot")
    readings: dict[int, list] = {}
    for r in db.scalars(select(BinReading).where(BinReading.ts >= since).order_by(BinReading.ts)):
        readings.setdefault(r.location_id, []).append([aware(r.ts).isoformat(), r.fill_pct])
    overflow_ids = sorted({r.location_id for r in db.scalars(select(Report).where(
        Report.kind == "overflow", Report.ts >= utcnow() - timedelta(hours=24))) if r.location_id})
    return {
        "plan_date": plan_date,
        "move_out": move_out,
        "depot": {"id": depot.id, "name": depot.name, "lat": depot.lat, "lng": depot.lng},
        "bins": [{"id": l.id, "name": l.name, "name_hi": hindi_name(l), "kind": l.kind, "lat": l.lat, "lng": l.lng, "capacity_l": l.capacity_l,
                  "readings": readings.get(l.id, [])} for l in locs if l.kind != "depot"],
        "overflow_location_ids": overflow_ids,
        "pickups": [{"id": p.id, "location_id": p.location_id, "material": p.material, "est_kg": p.est_kg}
                    for p in db.scalars(select(PickupRequest).where(PickupRequest.status == "pending"))],
        "collectors": [{"id": c.id, "name": c.name, "vehicle_capacity_kg": c.vehicle_capacity_kg} for c in db.scalars(select(Collector))],
    }


def text_hash(text: str) -> str:
    return hashlib.sha256(f"{config.ELEVENLABS_VOICE_ID}|{config.ELEVENLABS_TTS_MODEL}|{text}".encode()).hexdigest()


def store_result(db: Session, run: PlanRun, solved: dict) -> list[dict]:
    """Save routes. A briefing identical to one already voiced reuses that clip (has_audio=True → skip TTS)."""
    created = []
    for r in solved["routes"]:
        text = r.get("briefing_text", "")
        cached = db.scalars(select(AudioClip.id).where(AudioClip.text_hash == text_hash(text))).first()
        route = Route(plan_run_id=run.id, plan_date=run.plan_date, collector_id=r["collector_id"], stops=r["stops"],
                      distance_km=r["distance_km"], shift_min=r.get("shift_min", 0), briefing_text=text, audio_id=cached)
        db.add(route)
        db.flush()
        created.append({"route_id": route.id, "briefing_text": text, "collector_name": r["collector_name"], "has_audio": bool(cached)})
    for p in db.scalars(select(PickupRequest).where(PickupRequest.status == "pending")):
        p.status = "scheduled"
    run.summary = {"impact": planner.impact_summary(solved), "forecast": solved.get("forecast", {})}
    db.commit()
    return created


def store_audio(db: Session, route_id: int, mp3: bytes) -> int:
    route = db.get(Route, route_id)
    clip = AudioClip(data=mp3, text_hash=text_hash(route.briefing_text))
    db.add(clip)
    db.flush()
    route.audio_id = clip.id
    db.commit()
    return clip.id


def mark_step(db: Session, run: PlanRun, step: str) -> None:
    run.steps = [*(run.steps or []), step]  # reassign so SQLAlchemy notices the JSON change
    db.commit()


def run_locally(run_id: int, move_out: bool) -> None:
    """Fallback when Render Workflows isn't configured: same pipeline, in a thread."""
    with SessionLocal() as db:
        run = db.get(PlanRun, run_id)
        try:
            state = build_state(db, run.plan_date, move_out)
            mark_step(db, run, "load_state")
            solved = planner.run_pipeline(state, on_step=lambda step: mark_step(db, run, step))
            created = store_result(db, run, solved)
            mark_step(db, run, "publish_routes")
            for c in created:
                if c["has_audio"]:
                    continue
                try:  # audio is a bonus: a TTS failure must not lose the routes
                    mp3 = tts.synthesize(c["briefing_text"])
                except Exception as e:
                    run.summary = {**run.summary, "tts_error": str(e)[:300]}
                    continue
                if mp3:
                    store_audio(db, c["route_id"], mp3)
            mark_step(db, run, "synthesize_briefing")
            run.status = "done"
        except Exception as e:  # surface errors in the UI instead of hanging
            run.status = "failed"
            run.summary = {"error": str(e)}
        db.commit()


class PlanIn(BaseModel):
    plan_date: str | None = None
    move_out: bool = False


@app.post("/api/plan/run")
def plan_run(body: PlanIn, db: Session = Depends(get_db)):
    return start_plan(db, body.plan_date, body.move_out)


def start_plan(db: Session, plan_date: str | None, move_out: bool) -> dict:
    plan_date = plan_date or (datetime.now(IST).date() + timedelta(days=1)).isoformat()
    use_workflow = bool(config.RENDER_API_KEY and config.WORKFLOW_SLUG)
    run = PlanRun(plan_date=plan_date, engine="render_workflow" if use_workflow else "local")
    db.add(run)
    db.commit()
    if use_workflow:
        from render import Render
        task_run = Render().workflows.start_task(f"{config.WORKFLOW_SLUG}/plan_tomorrow",
                                                 {"plan_run_id": run.id, "plan_date": plan_date, "move_out": move_out})
        run.workflow_run_id = task_run.id
        db.commit()
    else:
        threading.Thread(target=run_locally, args=(run.id, move_out), daemon=True).start()
    return {"plan_run_id": run.id, "engine": run.engine, "workflow_run_id": run.workflow_run_id}


@app.get("/api/plan/runs/{run_id}")
def plan_status(run_id: int, db: Session = Depends(get_db)):
    run = db.get(PlanRun, run_id)
    if not run:
        raise HTTPException(404)
    if run.engine == "render_workflow" and run.status == "running" and run.workflow_run_id:
        try:
            from render import Render
            details = Render().workflows.get_task_run(run.workflow_run_id)
            if details.status.value in ("failed", "canceled"):
                run.status = "failed"
                run.summary = {"error": str(getattr(details, "error", "workflow failed"))}
                db.commit()
        except Exception:
            pass
    return {"id": run.id, "status": run.status, "engine": run.engine, "workflow_run_id": run.workflow_run_id,
            "plan_date": run.plan_date, "steps": run.steps or [], "all_steps": planner.PIPELINE_STEPS, "summary": {k: v for k, v in (run.summary or {}).items() if k != "forecast"}}


@app.get("/api/routes/latest")
def latest_routes(db: Session = Depends(get_db)):
    run = db.scalars(select(PlanRun).where(PlanRun.status == "done").order_by(PlanRun.id.desc())).first()
    if not run:
        return {"run": None, "routes": []}
    cnames = {c.id: c.name for c in db.scalars(select(Collector))}
    routes = db.scalars(select(Route).where(Route.plan_run_id == run.id)).all()
    return {
        "run": {"id": run.id, "plan_date": run.plan_date, "engine": run.engine, "workflow_run_id": run.workflow_run_id,
                "impact": (run.summary or {}).get("impact")},
        "routes": [{"id": r.id, "collector_id": r.collector_id, "collector_name": cnames.get(r.collector_id),
                    "stops": r.stops, "distance_km": r.distance_km, "shift_min": r.shift_min, "briefing_text": r.briefing_text,
                    "audio_url": f"{config.PUBLIC_BACKEND_URL}/api/audio/{r.audio_id}" if r.audio_id else None} for r in routes],
    }


@app.get("/api/audio/{clip_id}")
def audio(clip_id: int, db: Session = Depends(get_db)):
    clip = db.get(AudioClip, clip_id)
    if not clip:
        raise HTTPException(404)
    return Response(content=clip.data, media_type=clip.mime)


# ======================================================================= callbacks from Render Workflow tasks
@app.get("/internal/state", dependencies=[Depends(require_secret)])
def internal_state(plan_date: str, move_out: bool = False, db: Session = Depends(get_db)):
    return build_state(db, plan_date, move_out)


@app.post("/internal/plan-runs/{run_id}/result", dependencies=[Depends(require_secret)])
def internal_result(run_id: int, solved: dict, db: Session = Depends(get_db)):
    run = db.get(PlanRun, run_id)
    if not run:
        raise HTTPException(404)
    return {"routes": store_result(db, run, solved)}


class AudioIn(BaseModel):
    mp3_b64: str


@app.post("/internal/routes/{route_id}/audio", dependencies=[Depends(require_secret)])
def internal_audio(route_id: int, body: AudioIn, db: Session = Depends(get_db)):
    return {"audio_id": store_audio(db, route_id, base64.b64decode(body.mp3_b64))}


class StepIn(BaseModel):
    step: str


@app.post("/internal/plan-runs/{run_id}/step", dependencies=[Depends(require_secret)])
def internal_step(run_id: int, body: StepIn, db: Session = Depends(get_db)):
    run = db.get(PlanRun, run_id)
    if not run:
        raise HTTPException(404)
    mark_step(db, run, body.step)
    return {"ok": True}


class RunStatusIn(BaseModel):
    status: str
    error: str = ""


@app.post("/internal/plan-runs/{run_id}/status", dependencies=[Depends(require_secret)])
def internal_status(run_id: int, body: RunStatusIn, db: Session = Depends(get_db)):
    run = db.get(PlanRun, run_id)
    run.status = body.status
    if body.error:
        run.summary = {**(run.summary or {}), "error": body.error}
    db.commit()
    return {"ok": True}


# ======================================================================= ElevenLabs Agent tools
FILL_WORDS = [  # checked in order; Hindi/Hinglish/English
    (("overflow", "ubal", "bahar", "gir raha", "बाहर", "ओवरफ्लो"), 110),
    (("almost", "lagbhag", "करीब", "लगभग"), 80),
    (("full", "bhara", "bhar gaya", "poora", "भरा", "भर गया", "पूरा"), 95),
    (("half", "aadha", "आधा"), 50),
    (("empty", "khaali", "khali", "खाली"), 5),
]


def parse_fill(raw) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw or "").lower()
    try:
        return float(s.strip().rstrip("%"))
    except ValueError:
        pass
    for words, val in FILL_WORDS:
        if any(w in s for w in words):
            return val
    return 90.0


def find_collector(db: Session, collector_id: int | None, collector_name: str | None) -> Collector | None:
    if collector_id:
        return db.get(Collector, collector_id)
    if collector_name:
        from rapidfuzz import process
        cs = db.scalars(select(Collector)).all()
        hit = process.extractOne(collector_name.lower(), {c.id: c.name.lower() for c in cs})
        if hit and hit[1] >= 70:
            return db.get(Collector, hit[2])
    return None


class BinStatusIn(BaseModel):
    location_name: str
    fill_level: str | float = "full"
    waste_type: str = ""
    note: str = ""
    reporter_name: str = ""


@app.post("/tools/report_bin_status", dependencies=[Depends(require_secret)])
def tool_report_bin(body: BinStatusIn, db: Session = Depends(get_db)):
    loc, candidates = match_location(body.location_name, db.scalars(select(Location)).all())
    if not loc:
        return {"status": "need_clarification", "candidates": candidates,
                "message": f"Location not sure. Ask the caller which one: {', '.join(candidates)}"}
    fill = parse_fill(body.fill_level)
    kind = "overflow" if fill >= 100 else "fill_update"
    db.add(BinReading(location_id=loc.id, fill_pct=fill, source="voice"))
    db.add(Report(location_id=loc.id, kind=kind, text=f"{body.fill_level} {body.waste_type} {body.note}".strip(),
                  reporter=body.reporter_name or "collector", channel="voice"))
    db.commit()
    return {"status": "logged", "location": loc.name, "fill_pct": fill, "kind": kind,
            "message": f"Logged {loc.name} at {fill:.0f}%." + (" Marked as overflow — it will be prioritised in tomorrow's route." if kind == "overflow" else "")}


class CollectionIn(BaseModel):
    material: str
    kg: float = Field(..., gt=0, le=2000)
    location_name: str = ""
    collector_name: str = ""
    collector_id: int | None = None


def current_routes(db: Session) -> list[Route]:
    run = db.scalars(select(PlanRun).where(PlanRun.status == "done").order_by(PlanRun.id.desc())).first()
    return db.scalars(select(Route).where(Route.plan_run_id == run.id)).all() if run else []


def complete_stop(db: Session, collector: Collector | None, loc: Location) -> Route | None:
    """A collection at a planned stop ticks it off the route and closes any student pickup there."""
    routes = current_routes(db)
    mine = [r for r in routes if collector and r.collector_id == collector.id]
    route = next((r for r in mine + routes if any(s["location_id"] == loc.id for s in r.stops)), None)
    if route:
        route.stops = [{**s, "done": True, "done_at": utcnow().isoformat(), "done_by": collector.name if collector else ""}
                       if s["location_id"] == loc.id and not s.get("done") else s for s in route.stops]
    for p in db.scalars(select(PickupRequest).where(PickupRequest.location_id == loc.id,
                                                     PickupRequest.status.in_(["pending", "scheduled"]))):
        p.status = "collected"
    return route


def route_progress(route: Route | None) -> dict:
    if not route:
        return {}
    remaining = [s for s in route.stops if not s.get("done")]
    nxt = remaining[0] if remaining else None
    return {"stops_done": len(route.stops) - len(remaining), "stops_total": len(route.stops),
            "next_stop": nxt["name"] if nxt else None, "next_stop_hi": (nxt.get("name_hi") or nxt["name"]) if nxt else None}


@app.post("/tools/log_collection", dependencies=[Depends(require_secret)])
def tool_log_collection(body: CollectionIn, db: Session = Depends(get_db)):
    collector = find_collector(db, body.collector_id, body.collector_name)
    loc = None
    if body.location_name:
        loc, _ = match_location(body.location_name, db.scalars(select(Location)).all())
    mat = config.normalize_material(body.material)
    db.add(Collection(collector_id=collector.id if collector else None, location_id=loc.id if loc else None,
                      material=mat, kg=body.kg))
    route = None
    if loc:
        db.add(BinReading(location_id=loc.id, fill_pct=5, source="collected"))
        route = complete_stop(db, collector, loc)
    if collector:  # progress is always about the caller's own route, even if they helped at someone else's stop
        route = next((r for r in current_routes(db) if r.collector_id == collector.id), None)
    db.commit()
    start_of_day = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    q = select(func.sum(Collection.kg)).where(Collection.simulated.is_(False), Collection.ts >= start_of_day)
    if collector:
        q = q.where(Collection.collector_id == collector.id)
    today = db.scalar(q) or 0
    value = body.kg * config.MATERIALS[mat]["rate_inr_per_kg"]
    prog = route_progress(route)
    msg = f"Logged {body.kg:g} kg {config.MATERIALS[mat]['label']}, worth about ₹{value:.0f}. Today's total {today:.0f} kg."
    if prog:
        msg += (f" Route: {prog['stops_done']} of {prog['stops_total']} stops done. Next stop: {prog['next_stop_hi']}."
                if prog["next_stop"] else f" All {prog['stops_total']} stops on the route are done.")
    return {"status": "logged", "material": config.MATERIALS[mat]["label"], "material_hi": config.MATERIALS[mat]["label_hi"],
            "kg": body.kg, "location": loc.name if loc else None, "today_total_kg": round(today, 1), "value_inr": round(value),
            **prog, "message": msg}


class RouteQueryIn(BaseModel):
    collector_name: str = ""
    collector_id: int | None = None


@app.post("/tools/get_my_route", dependencies=[Depends(require_secret)])
def tool_get_route(body: RouteQueryIn, db: Session = Depends(get_db)):
    collector = find_collector(db, body.collector_id, body.collector_name)
    if not collector:
        names = [c.name for c in db.scalars(select(Collector))]
        return {"status": "need_clarification", "message": f"Ask the caller their name. Known collectors: {', '.join(names)}"}
    route = next((r for r in current_routes(db) if r.collector_id == collector.id), None)
    if not route:
        return {"status": "no_route", "message": f"No route planned for {collector.name} yet."}
    remaining = [s for s in route.stops if not s.get("done")]
    return {"status": "ok", "collector": collector.name, "plan_date": route.plan_date, "distance_km": route.distance_km,
            **route_progress(route),
            "remaining_stops": [{"order": i + 1, "name": s.get("name_hi") or s["name"], "why": ", ".join(s["reasons"]),
                                 "est_kg": s["est_kg"], "trip": s.get("trip", 1)} for i, s in enumerate(remaining)],
            "message": "All stops done." if not remaining else f"{len(remaining)} stops left; read them in order."}
