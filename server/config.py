"""All tunable numbers live here. Sources for every factor are listed in README → "Sources & assumptions"."""
import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./kabaad.db")
# Render gives postgres:// URLs; SQLAlchemy + psycopg3 wants postgresql+psycopg://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

TOOL_SHARED_SECRET = os.getenv("TOOL_SHARED_SECRET", "dev-secret")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")  # pick a Hindi voice from the ElevenLabs voice library
ELEVENLABS_TTS_MODEL = os.getenv("ELEVENLABS_TTS_MODEL", "eleven_multilingual_v2")

# Render Workflows. WORKFLOW_SLUG = the name of your Workflow service on Render.
RENDER_API_KEY = os.getenv("RENDER_API_KEY", "")
WORKFLOW_SLUG = os.getenv("WORKFLOW_SLUG", "")
# Where workflow tasks call back to (the backend's public or private URL).
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
PUBLIC_BACKEND_URL = os.getenv("PUBLIC_BACKEND_URL", BACKEND_URL)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
AUTO_PLAN_AT_IST = os.getenv("AUTO_PLAN_AT_IST", "21:00")  # nightly "Plan tomorrow"; set empty to disable

# --- Planning knobs ---------------------------------------------------------
FILL_THRESHOLD = 75          # % predicted fill at which a bin gets a stop tomorrow
TRIPS_PER_COLLECTOR = 3     # depot round trips a collector can make in one shift
# Shift-time model used to balance work across collectors (assumptions, see README)
CART_KMPH = 12               # loaded e-cart / tipper on campus roads
STOP_MIN = 4                 # park, walk to the bin, back
LOAD_MIN_PER_100KG = 6       # manual loading
UNLOAD_MIN = 12              # tip + sort at the depot between trips
BALANCE_M_PER_MIN = 150      # objective: 1 min of longest shift costs as much as 150 m of driving (sweep: spread 46→5 min for +1.2 km)
ROAD_FACTOR = 1.35           # straight-line -> road distance multiplier
KG_PER_LITRE = 0.12          # loose mixed campus dry waste in a bin, ~120 kg/m³ (assumption, see README)
MOVE_OUT_MULTIPLIER = 2.5    # semester-end move-out spike
DIESEL_L_PER_KM = 0.08       # ~12.5 km/L, small diesel tipper in stop-start campus duty (assumption)
CO2_KG_PER_L_DIESEL = 2.68   # IPCC 2006 default for diesel (74.1 t CO₂/TJ)

# --- Materials -------------------------------------------------------------
# rate_inr_per_kg: TheKabadiwala doorstep rate list (Delhi), accessed 2026-10-24 — what a household is paid;
#   a collector selling on to a dealer gets more, so these are conservative. Glass isn't on the list (estimate).
# co2e_avoided_per_kg: US EPA WARM v16 (Dec 2023) recycling emission factors, MTCO2E/short ton × 1.1023 → kg/kg.
#   Metal uses steel cans (2.02), not aluminium cans (10.06), to stay conservative. E-waste, organic, MLP and
#   mixed are not credited (0).
MATERIALS = {
    "cardboard": {"label": "Paper & cardboard", "label_hi": "गत्ता / कागज़", "rate_inr_per_kg": 6,  "co2e_avoided_per_kg": 3.46},  # carton ₹6; WARM corrugated −3.14
    "pet":       {"label": "PET bottles",       "label_hi": "पेट बोतल",     "rate_inr_per_kg": 10, "co2e_avoided_per_kg": 1.15},  # PET bottle ₹10; WARM PET −1.04
    "hdpe":      {"label": "HDPE / hard plastic","label_hi": "सख़्त प्लास्टिक", "rate_inr_per_kg": 5,  "co2e_avoided_per_kg": 0.84},  # hard plastic ₹5; WARM HDPE −0.76
    "metal":     {"label": "Metal & cans",      "label_hi": "लोहा / डिब्बे",  "rate_inr_per_kg": 15, "co2e_avoided_per_kg": 2.02},  # tin ₹15; WARM steel cans −1.83
    "ewaste":    {"label": "E-waste",           "label_hi": "ई-कचरा",       "rate_inr_per_kg": 10, "co2e_avoided_per_kg": 0.0},   # printer/laptop ₹7–10
    "glass":     {"label": "Glass",             "label_hi": "काँच",         "rate_inr_per_kg": 1,  "co2e_avoided_per_kg": 0.31},  # estimate; WARM glass −0.28
    "mlp":       {"label": "Multilayer (MLP)",  "label_hi": "पन्नी / चिप्स पैकेट", "rate_inr_per_kg": 0, "co2e_avoided_per_kg": 0.0},  # "packaging film ₹0"
    "organic":   {"label": "Organic / food",    "label_hi": "गीला कचरा",     "rate_inr_per_kg": 0,  "co2e_avoided_per_kg": 0.0},
    "mixed":     {"label": "Mixed / unsorted",  "label_hi": "मिला हुआ",      "rate_inr_per_kg": 0,  "co2e_avoided_per_kg": 0.0},
}

MATERIAL_ALIASES = {
    "gatta": "cardboard", "गत्ता": "cardboard", "carton": "cardboard", "paper": "cardboard", "kagaz": "cardboard", "कागज़": "cardboard", "raddi": "cardboard", "रद्दी": "cardboard",
    "bottle": "pet", "bottles": "pet", "बोतल": "pet", "plastic bottle": "pet",
    "plastic": "hdpe", "प्लास्टिक": "hdpe", "bucket": "hdpe",
    "loha": "metal", "लोहा": "metal", "can": "metal", "cans": "metal", "tin": "metal",
    "e-waste": "ewaste", "electronic": "ewaste", "charger": "ewaste",
    "kaanch": "glass", "काँच": "glass",
    "panni": "mlp", "पन्नी": "mlp", "chips packet": "mlp", "wrapper": "mlp",
    "khana": "organic", "food": "organic", "गीला": "organic", "wet": "organic",
}


def normalize_material(raw: str | None) -> str:
    if not raw:
        return "mixed"
    s = raw.strip().lower()
    if s in MATERIALS:
        return s
    for alias, key in MATERIAL_ALIASES.items():
        if alias in s:
            return key
    return "mixed"
