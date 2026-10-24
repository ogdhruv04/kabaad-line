"""Seed the database with campus locations, collectors and 14 days of SIMULATED history.

Coordinates come from OpenStreetMap (Overpass API, queried 2026-10-24; © OpenStreetMap contributors).
Exceptions, marked "approx" below: the depot (no MRF/estate yard is mapped) and Azad Bhawan (only its
stationery shop is mapped).

Run:  python -m server.seed          (wipes and reseeds)
"""
import random
from datetime import datetime, timedelta, timezone

from .db import Base, SessionLocal, engine
from .models import BinReading, Collection, Collector, Location, Report

# name, kind, (lat, lng), capacity_l, aliases
LOCATIONS = [
    ("Estate Depot (MRF)",     "depot",  (29.86500, 77.89060), 0,    ["depot", "estate", "डिपो", "एस्टेट"]),  # approx
    ("Rajendra Bhawan",        "hostel", (29.87101, 77.89408), 1100, ["rajendra", "rjb", "राजेंद्र", "राजेंद्र भवन"]),
    ("Govind Bhawan",          "hostel", (29.86203, 77.89447), 1100, ["govind", "गोविंद", "गोविंद भवन"]),
    ("Cautley Bhawan",         "hostel", (29.87055, 77.89684), 1100, ["cautley", "कॉटली", "कॉटली भवन"]),
    ("Ganga Bhawan",           "hostel", (29.87173, 77.89454), 1100, ["ganga", "गंगा", "गंगा भवन"]),
    ("Jawahar Bhawan",         "hostel", (29.86369, 77.90095), 1100, ["jawahar", "जवाहर", "जवाहर भवन"]),
    ("Ravindra Bhawan",        "hostel", (29.86493, 77.89282), 1100, ["ravindra", "रविंद्र", "रवींद्र भवन"]),
    ("Azad Bhawan",            "hostel", (29.86536, 77.89219), 1100, ["azad", "आज़ाद", "आजाद भवन"]),  # approx
    ("Rajiv Bhawan",           "hostel", (29.86978, 77.89498), 1100, ["rajiv", "राजीव", "राजीव भवन"]),
    ("Radhakrishnan Bhawan",   "hostel", (29.87120, 77.89566), 1100, ["radhakrishnan", "rkb", "राधाकृष्णन"]),
    ("Kasturba Bhawan",        "hostel", (29.86724, 77.90090), 1100, ["kasturba", "kb", "कस्तूरबा", "कस्तूरबा भवन"]),
    ("Sarojini Bhawan",        "hostel", (29.86505, 77.90003), 1100, ["sarojini", "सरोजिनी", "सरोजिनी भवन"]),
    ("Himalaya Bhawan",        "hostel", (29.86113, 77.89618), 1100, ["himalaya", "हिमालय", "हिमालय भवन"]),
    ("Vigyan Kunj",            "hostel", (29.86215, 77.90030), 1100, ["vigyan", "vigyan kunj", "विज्ञान कुंज"]),
    ("Cautley-Ganga Mess",     "mess",   (29.87199, 77.89520), 660,  ["mess", "cautley ganga mess", "ganga mess", "cautley mess", "मेस"]),
    ("Main Building",          "dept",   (29.86465, 77.89657), 660,  ["main building", "mb", "james thomason", "मेन बिल्डिंग"]),
    ("Lecture Hall Complex",   "dept",   (29.86482, 77.89390), 660,  ["lhc", "lecture hall", "एलएचसी"]),
    ("Central Library",        "dept",   (29.86531, 77.89477), 660,  ["library", "mgcl", "लाइब्रेरी"]),
    ("Multi Activity Centre",  "dept",   (29.87014, 77.89636), 660,  ["mac", "activity centre", "मैक"]),
    ("Institute Hospital",     "dept",   (29.86172, 77.89292), 660,  ["hospital", "अस्पताल"]),
    ("Civil Engg Dept",        "dept",   (29.86261, 77.89854), 660,  ["civil", "सिविल"]),
    ("Electrical Engg Dept",   "dept",   (29.86367, 77.89732), 660,  ["electrical", "ee dept", "इलेक्ट्रिकल"]),
    ("Students Club Canteen",  "mess",   (29.86392, 77.89463), 660,  ["canteen", "students club", "कैंटीन"]),
    ("Sports Complex",         "dept",   (29.86776, 77.89883), 660,  ["sports", "stadium", "dhyan chand", "स्पोर्ट्स"]),
    ("Main Gate Market",       "dept",   (29.86543, 77.88935), 660,  ["main gate", "market", "मेन गेट", "बाज़ार"]),
    ("Saraswati Kunj",         "bin",    (29.86984, 77.89821), 660,  ["saraswati kunj", "faculty", "residence", "सरस्वती कुंज", "क्वार्टर"]),
]

COLLECTORS = [
    ("Ramesh", "+910000000001", 600),
    ("Sunita", "+910000000002", 500),
    ("Iqbal",  "+910000000003", 550),
]

# Daily fill rate (% of capacity per day) by kind, before noise
DAILY_RATE = {"hostel": 38, "mess": 55, "dept": 22, "bin": 18, "depot": 0}
HOSTEL_WEEKEND_BOOST = 1.3
MATERIAL_MIX = {"cardboard": 0.28, "pet": 0.14, "hdpe": 0.06, "metal": 0.04, "glass": 0.03, "ewaste": 0.01, "mlp": 0.16, "mixed": 0.28}


def seed(days: int = 14, rng_seed: int = 7) -> None:
    rng = random.Random(rng_seed)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()

    locs = []
    for name, kind, (lat, lng), cap, aliases in LOCATIONS:
        loc = Location(name=name, kind=kind, lat=lat, lng=lng, capacity_l=cap, aliases=aliases)
        db.add(loc)
        locs.append(loc)
    collectors = [Collector(name=n, phone=p, vehicle_capacity_kg=c) for n, p, c in COLLECTORS]
    db.add_all(collectors)
    db.flush()

    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = now - timedelta(days=days)
    bins = [l for l in locs if l.kind != "depot"]
    fill = {b.id: rng.uniform(5, 40) for b in bins}

    t = start
    step = timedelta(hours=6)
    while t <= now:
        weekend = t.weekday() >= 5
        for b in bins:
            rate = DAILY_RATE[b.kind] * rng.uniform(0.7, 1.3)
            if b.kind == "hostel" and weekend:
                rate *= HOSTEL_WEEKEND_BOOST
            fill[b.id] += rate / 4  # 6-hour step
            # Fixed-schedule collection (the status quo we compare against): one morning round per day;
            # if above 60%, otherwise it overflows.
            if (t - start).total_seconds() % 86400 == 0 and fill[b.id] >= 60:
                kg = b.capacity_l * min(fill[b.id], 110) / 100 * 0.12
                for mat, share in MATERIAL_MIX.items():
                    db.add(Collection(collector_id=rng.choice(collectors).id, location_id=b.id, material=mat,
                                      kg=round(kg * share * rng.uniform(0.8, 1.2), 1), simulated=True, ts=t))
                fill[b.id] = rng.uniform(0, 8)
            if fill[b.id] > 100 and rng.random() < 0.15:
                db.add(Report(location_id=b.id, kind="overflow", text="Bin overflowing (simulated)",
                              reporter="sim", channel="voice", simulated=True, ts=t))
            db.add(BinReading(location_id=b.id, fill_pct=round(min(fill[b.id], 120), 1), source="sensor_sim", ts=t))
        t += step

    db.commit()
    db.close()
    print(f"Seeded {len(locs)} locations, {len(collectors)} collectors, {days} days of simulated history.")


if __name__ == "__main__":
    seed()
