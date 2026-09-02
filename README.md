# SafePlace — Offline AI Safety Copilot

> **Concept**: An offline-first AI safety copilot that helps a person find the safest reachable place and route, explains why it made the recommendation, continuously monitors a dynamic safety bubble, and explicitly knows when available evidence is insufficient.

---

## 🌟 Key Innovations

1. **Offline-First AI Architecture**: Runs completely on-device without internet or cellular connectivity using local SQLite spatial indexing, Graph routing, and an on-device SLM Copilot (LiteRT-LM / Gemma).
2. **Safe Route vs. Fastest Route**: Rather than optimizing only for distance or travel time, SafePlace computes risk penalties based on street lighting, dedicated footpaths, CCTV coverage, and emergency service proximity.
3. **Uncertainty-Aware AI ("I Don't Know" Mechanism)**: When local safety evidence becomes stale (>2 weeks old) or incomplete, confidence drops below 40% and the AI explicitly abstains rather than hallucinating an ungrounded safety guarantee.
4. **Dynamic Safe Bubble**: Continuously calculates trusted havens (Police, Hospitals, 24/7 Pharmacies, Shelters) reachable within 5, 10, and 15-minute isochrones.
5. **Emergency Mode ("I'M NOT SAFE")**: One-tap trigger that instantly identifies the highest-confidence safety haven, highlights the safe corridor, and provides spoken voice navigation.
6. **Data Trust Layer**: Evaluates source pedigree, freshness half-life decay, attribute completeness, and verification status.

---

## 🏗️ Project Architecture

```
SafePlace
├── run.py                          # One-click launcher (seeds DB, starts server & opens UI)
├── requirements.txt                # Python dependencies (FastAPI, NetworkX, Pytest, etc.)
├── config.py                       # System weights, confidence thresholds & config
│
├── core/                           # Offline Intelligence Engines
│   ├── models.py                   # Pydantic data schemas (POI, RoadSegment, Route, SafeBubble)
│   ├── database.py                 # SQLite Spatial & Offline Data Store
│   ├── risk_engine.py              # Safety Risk Scoring Model (0-100 score)
│   ├── confidence_engine.py        # Data Trust & "I Don't Know" Abstention Engine
│   ├── route_engine.py             # Safe vs. Fast Pathfinding (NetworkX A*/Dijkstra)
│   ├── safe_bubble.py              # Dynamic Safe Bubble Isochrone Monitor
│   └── slm_engine.py               # On-device SLM Copilot with Controlled Tools & Guardrails
│
├── data/                           # Data Foundry & Pre-packaged GIS Data
│   ├── dataset_builder.py          # Google Foundry GIS builder & SQLite seeder
│   ├── sample_city_data.json       # Structured benchmark dataset
│   └── safeplace_offline.db        # Built local SQLite database
│
├── api/                            # Backend REST API
│   ├── server.py                   # FastAPI server & static mounts
│   └── routes.py                   # REST endpoints (/api/pois, /api/safe-bubble, /api/route, /api/emergency, /api/chat)
│
├── ui/                             # Interactive Web HUD & Map Dashboard
│   ├── index.html                  # Leaflet map interface, Emergency HUD, AI Chat
│   ├── css/style.css               # Clean safety theme (dark glassmorphism)
│   └── js/app.js                   # Interactive map controller, GPS simulator & Voice UI
│
└── tests/                          # Automated Pytest Suite (19 test cases)
    ├── test_database.py            # SQLite spatial queries & distance checks
    ├── test_risk_engine.py         # Multi-factor risk calculation tests
    ├── test_confidence_engine.py   # Freshness decay & abstention tests
    ├── test_route_engine.py        # Fastest vs. Safest route comparison tests
    ├── test_safe_bubble.py         # Dynamic isochrone reachability tests
    ├── test_slm_copilot.py         # SLM tool execution & grounded reasoning tests
    └── test_api.py                 # FastAPI REST endpoint integration tests
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 2. Launch SafePlace
```bash
python run.py
```
This automatically seeds the offline database, boots the FastAPI server at `http://127.0.0.1:8000`, and opens the interactive dashboard in your web browser.

---

## 🧪 Running Automated Tests

Run the complete test suite with verbose output:
```bash
python -m pytest tests/ -v
```
All 19 test cases validate spatial indexing, risk scoring, confidence decay, safe vs fast routing, dynamic safe bubble, SLM tool orchestration, and API endpoints.

---

## 🎬 How to Perform the "Patchamama WOW Demo"

1. **Explore Indian City Presets**: Select from the top bar dropdown:
   - 🇮🇳 **Hyderabad (HITEC City / Madhapur)**: Includes Cyberabad Police Station, Medicover Hospital, Apollo Pharmacy 24/7, HITEC City Metro, and Guttala Begumpet alley shortcut.
   - 🇮🇳 **Bangalore (MG Road / Indiranagar)**: Includes Cubbon Park Police Station, Manipal Hospital, MedPlus 24/7, MG Road Metro.
   - 🇮🇳 **Delhi (Connaught Place)** & 🇮🇳 **Mumbai (Bandra / BKC)**.
2. **Use Your Real GPS in India**: Click the **"📍 Locate Me"** button in the header bar. SafePlace will read your real GPS coordinates from your device and dynamically generate a verified local safety network with illuminated corridors and emergency havens around your exact location!
3. **Move GPS Position**: Drag the blue user marker on the map to see the **Safe Bubble** concentric rings (5m, 10m, 15m) dynamically recalculate.
4. **Compare Safe vs. Fast Routes**: Click on **Cyberabad Police Station** and toggle between:
   - **Safest Route** (Green line): Follows HITEC City Main Boulevard (100% lighting, 98% safety).
   - **Fastest Route** (Amber dashed line): Cuts through the dark Guttala Begumpet alley (saves 0.7 min, but drops lighting to 15% with higher hazard risk).
5. **Trigger Emergency Mode**: Click the large red **"I'M NOT SAFE"** button for instant emergency routing and spoken turn-by-turn guidance.
6. **Demonstrate Uncertainty & "I Don't Know" Abstention**:
   - Drag the **Data Age slider** in the top bar from `0h` to `720h` (1 month old).
   - Ask the AI Copilot: *"Where is the safest place I can go right now?"*
   - Watch the AI dynamically detect stale data, decrease confidence, and explicitly **abstain** (*"I don't have enough recent information to make a reliable safety recommendation..."*) rather than guessing!
7. **Re-sync Data**: Click **"Sync Data"** to refresh verified municipal packages back to 100% confidence.

---

## 📜 Responsible AI Guardrails (Appendix B)

- **No False Guarantees**: Uses "estimated risk" and "confidence", never claims absolute safety.
- **Uncertainty Awareness**: Explicitly abstains when data is stale, missing, or contradictory.
- **Transparent Evidence**: Every recommendation provides grounded evidence (lighting %, infrastructure quality, distance, data age).
- **Privacy First**: All core processing is on-device with zero location telemetry transmission.
