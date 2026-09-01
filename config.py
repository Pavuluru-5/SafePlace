"""
SafePlace — Configuration and Parameters
Based on SafePlace Product & Technical Documentation (Patchamama 2026).
"""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "data" / "safeplace_offline.db"
SAMPLE_DATA_PATH = BASE_DIR / "data" / "sample_city_data.json"
UI_DIR = BASE_DIR / "ui"

# Server Configuration
SERVER_HOST = os.environ.get("HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("PORT", 8000))

# Safety Risk Engine Prototype Weightings (Section 10 of Documentation)
RISK_WEIGHTS = {
    "infrastructure": 0.25,        # Road type, lanes, physical condition
    "emergency_proximity": 0.20,   # Proximity to police, hospitals, fire stations
    "activity_proxy": 0.15,        # Public activity, commercial presence, foot traffic proxy
    "incident_pattern": 0.15,      # Historical aggregated incident density (inverse penalty)
    "lighting": 0.10,              # Well-lit vs dark segments
    "accessibility": 0.10,         # Footpath availability, pedestrian access
    "data_freshness": 0.05         # Freshness of safety evidence
}

# Confidence & Data Trust Engine Weights (Section 11)
CONFIDENCE_WEIGHTS = {
    "source_quality": 0.35,        # Official municipal vs crowdsourced vs estimated
    "freshness": 0.30,             # Time decay factor
    "completeness": 0.20,          # Presence of required spatial & safety attributes
    "verification": 0.15           # Verified status by local authority or system check
}

# Confidence Thresholds for "I Don't Know" Abstention (Section 12)
CONFIDENCE_THRESHOLDS = {
    "HIGH": 80.0,       # Strong recommendation
    "MODERATE": 50.0,   # Recommendation with caution
    "LOW": 40.0,        # Limited recommendation / alternatives
    "ABSTAIN": 40.0     # Below this threshold, SafePlace explicitly abstains ("I don't know")
}

# Safe Bubble Time Windows in minutes (Section 15)
SAFE_BUBBLE_WINDOWS_MIN = [5, 10, 15]

# Average Travel Speeds (km/h)
WALKING_SPEED_KMH = 4.5
DRIVING_SPEED_KMH = 30.0

# Safe vs Fast Routing Trade-off Multipliers (Section 13)
# Route Score = Travel Cost + Safety Cost (Risk Penalty) + Uncertainty Cost
ROUTING_WEIGHTS = {
    "travel_time_weight": 1.0,
    "risk_penalty_weight": 2.2,
    "uncertainty_penalty_weight": 1.5
}
