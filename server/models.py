from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class Location(Base):
    __tablename__ = "locations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    aliases: Mapped[list] = mapped_column(JSON, default=list)  # English, Hinglish and Devanagari spellings
    kind: Mapped[str] = mapped_column(String(20))  # bin | hostel | mess | dept | depot
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    capacity_l: Mapped[int] = mapped_column(Integer, default=660)


class Collector(Base):
    __tablename__ = "collectors"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(20), default="")
    language: Mapped[str] = mapped_column(String(10), default="hi")
    vehicle_capacity_kg: Mapped[int] = mapped_column(Integer, default=400)


class BinReading(Base):
    __tablename__ = "bin_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    fill_pct: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20))  # sensor_sim | voice | student | collected
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(30))  # overflow | fill_update | missed_pickup | dumping | other
    text: Mapped[str] = mapped_column(Text, default="")
    reporter: Mapped[str] = mapped_column(String(80), default="")
    channel: Mapped[str] = mapped_column(String(20), default="voice")  # voice | web
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class Collection(Base):
    __tablename__ = "collections"
    id: Mapped[int] = mapped_column(primary_key=True)
    collector_id: Mapped[int | None] = mapped_column(ForeignKey("collectors.id"), nullable=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    material: Mapped[str] = mapped_column(String(20))
    kg: Mapped[float] = mapped_column(Float)
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class PickupRequest(Base):
    __tablename__ = "pickup_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    material: Mapped[str] = mapped_column(String(20))
    est_kg: Mapped[float] = mapped_column(Float, default=5)
    contact: Mapped[str] = mapped_column(String(120), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | scheduled | done
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PlanRun(Base):
    __tablename__ = "plan_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_date: Mapped[str] = mapped_column(String(10))
    engine: Mapped[str] = mapped_column(String(20))  # render_workflow | local
    workflow_run_id: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(20), default="running")
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    steps: Mapped[list] = mapped_column(JSON, default=list)  # pipeline steps finished so far, in order
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Route(Base):
    __tablename__ = "routes"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_run_id: Mapped[int] = mapped_column(ForeignKey("plan_runs.id"), index=True)
    plan_date: Mapped[str] = mapped_column(String(10), index=True)
    collector_id: Mapped[int] = mapped_column(ForeignKey("collectors.id"))
    stops: Mapped[list] = mapped_column(JSON, default=list)  # [{location_id, name, lat, lng, est_kg, reason}]
    distance_km: Mapped[float] = mapped_column(Float, default=0)
    briefing_text: Mapped[str] = mapped_column(Text, default="")
    audio_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AudioClip(Base):
    __tablename__ = "audio_clips"
    id: Mapped[int] = mapped_column(primary_key=True)
    mime: Mapped[str] = mapped_column(String(40), default="audio/mpeg")
    text_hash: Mapped[str] = mapped_column(String(64), default="", index=True)  # same briefing → reuse clip, save TTS credits
    data: Mapped[bytes] = mapped_column(LargeBinary)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
