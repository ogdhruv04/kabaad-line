"""All tunable numbers live here. Replace the placeholder factors with sourced values before judging."""
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

# --- Planning knobs ---------------------------------------------------------
FILL_THRESHOLD = 75          # % predicted fill at which a bin gets a stop tomorrow
TRIPS_PER_COLLECTOR = 3     # depot round trips a collector can make in one shift
ROAD_FACTOR = 1.35           # straight-line -> road distance multiplier
KG_PER_LITRE = 0.12          # mixed campus dry waste bulk density (placeholder)
MOVE_OUT_MULTIPLIER = 2.5    # semester-end move-out spike
DIESEL_L_PER_KM = 0.12       # small tipper / e-cart equivalent (placeholder)
CO2_KG_PER_L_DIESEL = 2.68

# --- Materials -------------------------------------------------------------
# rate_inr_per_kg: rough Roorkee kabadi rates — REPLACE with rates you get from a real kabadiwala today.
# co2e_avoided_per_kg: PLACEHOLDER factors — replace with sourced numbers (e.g. US EPA WARM) and cite in README.
MATERIALS = {
    "cardboard": {"label": "Paper & cardboard", "label_hi": "गत्ता / कागज़", "rate_inr_per_kg": 10, "co2e_avoided_per_kg": 0.9},
    "pet":       {"label": "PET bottles",       "label_hi": "पेट बोतल",     "rate_inr_per_kg": 18, "co2e_avoided_per_kg": 1.5},
    "hdpe":      {"label": "HDPE / hard plastic","label_hi": "सख़्त प्लास्टिक", "rate_inr_per_kg": 22, "co2e_avoided_per_kg": 1.0},
    "metal":     {"label": "Metal & cans",      "label_hi": "लोहा / डिब्बे",  "rate_inr_per_kg": 30, "co2e_avoided_per_kg": 4.0},
    "ewaste":    {"label": "E-waste",           "label_hi": "ई-कचरा",       "rate_inr_per_kg": 40, "co2e_avoided_per_kg": 2.0},
    "glass":     {"label": "Glass",             "label_hi": "काँच",         "rate_inr_per_kg": 2,  "co2e_avoided_per_kg": 0.3},
    "mlp":       {"label": "Multilayer (MLP)",  "label_hi": "पन्नी / चिप्स पैकेट", "rate_inr_per_kg": 0, "co2e_avoided_per_kg": 0.0},
    "organic":   {"label": "Organic / food",    "label_hi": "गीला कचरा",     "rate_inr_per_kg": 0,  "co2e_avoided_per_kg": 0.5},
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
