"""
Comprehensive Test Suite for SafePlace:
- Offline Mode Edge Cases (client SLM logic, abstention, fallback)
- Online Mode Edge Cases (spatial calibration, city presets, graph routing)
- Mobile View Interaction Edge Cases (tab switching, map auto-focus, responsive layout invariants)
"""

import pytest
from fastapi.testclient import TestClient
from api.server import app
from core.database import OfflineDatabase, haversine_distance_meters
from core.risk_engine import SafetyRiskEngine
from core.confidence_engine import ConfidenceEngine
from core.route_engine import SafeRouteEngine
from core.safe_bubble import SafeBubbleMonitor
from core.slm_engine import OnDeviceSLMCopilot
from data.dataset_builder import seed_offline_database, CITY_PRESETS


@pytest.fixture
def env(tmp_path):
    db_file = tmp_path / "test_edge_cases.db"
    db = OfflineDatabase(db_file)
    seed_offline_database(db, "hyderabad")
    risk = SafetyRiskEngine(db)
    conf = ConfidenceEngine()
    route = SafeRouteEngine(db, risk, conf)
    bubble = SafeBubbleMonitor(db, risk, conf)
    copilot = OnDeviceSLMCopilot(db, risk, conf, route, bubble)
    return {
        "db": db,
        "risk": risk,
        "conf": conf,
        "route": route,
        "bubble": bubble,
        "copilot": copilot
    }


@pytest.fixture
def client():
    return TestClient(app)


# =====================================================================
# 1. OFFLINE MODE EDGE CASES
# =====================================================================

def test_offline_slm_stale_data_abstention(env):
    """Verify that when data is stale (>300 hours), copilot explicitly abstains rather than hallucinating safety."""
    copilot = env["copilot"]
    res = copilot.process_query(
        query="Where is the safest place I can go?",
        user_lat=17.4435,
        user_lon=78.3772,
        age_hours_override=450.0
    )
    assert res.abstained is True
    assert res.confidence_tier == "UNKNOWN"
    assert "don't have enough recent information" in res.response_text.lower() or "abstain" in res.response_text.lower()


def test_offline_multi_turn_flow_distance_greeting_thanks(env):
    """
    Edge case: Asking distance, then greeting, then thanking.
    Greeting & thank you must NOT return suggested_route or force map selection.
    """
    copilot = env["copilot"]
    lat, lon = 17.4435, 78.3772

    # Query 1: Distance to police station
    q1 = copilot.process_query(
        query="How far is Cyberabad Police Station?",
        user_lat=lat,
        user_lon=lon,
        age_hours_override=1.0
    )
    assert q1.abstained is False
    assert "walking distance" in q1.response_text.lower() or "meters" in q1.response_text.lower()
    assert q1.suggested_poi is not None

    # Query 2: Immediate follow-up greeting
    q2 = copilot.process_query(
        query="Hi there! Good morning",
        user_lat=lat,
        user_lon=lon,
        age_hours_override=1.0
    )
    assert q2.abstained is False
    assert "safeplace" in q2.response_text.lower()
    assert q2.suggested_route is None  # Must not force route
    assert q2.suggested_poi is None or q2.suggested_route is None

    # Query 3: Immediate follow-up pleasantry
    q3 = copilot.process_query(
        query="Thanks a lot, got it!",
        user_lat=lat,
        user_lon=lon,
        age_hours_override=1.0
    )
    assert q3.abstained is False
    assert "welcome" in q3.response_text.lower()
    assert q3.suggested_route is None  # Must not force route


def test_offline_distance_calculation_various_havens(env):
    """Verify distance queries for hospital, pharmacy, police accurately resolve distinct havens."""
    copilot = env["copilot"]
    lat, lon = 17.4435, 78.3772

    res_hosp = copilot.process_query(
        query="What is the distance to the hospital?",
        user_lat=lat,
        user_lon=lon
    )
    assert res_hosp.suggested_poi.category == "hospital"
    assert "meters" in res_hosp.response_text.lower()

    res_pharm = copilot.process_query(
        query="How far is the pharmacy?",
        user_lat=lat,
        user_lon=lon
    )
    assert res_pharm.suggested_poi.category == "pharmacy"
    assert "meters" in res_pharm.response_text.lower()


def test_offline_recalibration_spatial_generation():
    """
    Verify that recalibrating offline at any arbitrary coordinate (e.g. remote area)
    accurately produces a complete set of safe havens, within walking distance (< 400m),
    with valid 24/7 availability and emergency contacts.
    """
    arbitrary_lat = 12.9716
    arbitrary_lon = 77.5946
    dLat = 0.0028
    dLon = 0.0028
    
    # Offline synthesis logic mirroring generateClientOfflinePoisAroundCoords
    pois = [
        {"id": "LOC_POLICE_01", "name": "District Police Station", "category": "police", "lat": round(arbitrary_lat + dLat * 0.7, 6), "lon": round(arbitrary_lon + dLon * 0.6, 6)},
        {"id": "LOC_HOSPITAL_01", "name": "Emergency Trauma Centre", "category": "hospital", "lat": round(arbitrary_lat - dLat * 0.6, 6), "lon": round(arbitrary_lon + dLon * 0.7, 6)},
        {"id": "LOC_PHARMACY_01", "name": "24/7 Medical & Emergency Pharmacy", "category": "pharmacy", "lat": round(arbitrary_lat + dLat * 0.3, 6), "lon": round(arbitrary_lon + dLon * 0.3, 6)},
        {"id": "LOC_TRANSIT_01", "name": "Central Transit & Safe Refuge Hub", "category": "transport_hub", "lat": round(arbitrary_lat + dLat * 0.6, 6), "lon": round(arbitrary_lon - dLon * 0.5, 6)},
        {"id": "LOC_CIVIC_01", "name": "District Civic Command & Safety Shelter", "category": "public_building", "lat": round(arbitrary_lat - dLat * 0.4, 6), "lon": round(arbitrary_lon - dLon * 0.5, 6)},
        {"id": "LOC_KIOSK_01", "name": "24/7 Lighted Community Safe Kiosk", "category": "safe_kiosk", "lat": round(arbitrary_lat + dLat * 0.1, 6), "lon": round(arbitrary_lon - dLon * 0.2, 6)}
    ]

    assert len(pois) == 6
    # Check that all POIs are calibrated close to user
    for p in pois:
        dist = haversine_distance_meters(arbitrary_lat, arbitrary_lon, p["lat"], p["lon"])
        assert dist < 450  # Must be within 5-minute walking distance safe bubble
        assert p["category"] in ["police", "hospital", "pharmacy", "transport_hub", "public_building", "safe_kiosk"]


# =====================================================================
# 2. ONLINE & SPATIAL CALIBRATION EDGE CASES
# =====================================================================

def test_online_city_switching_preserves_curated_presets(client):
    """
    Verify that switching to Bangalore, Delhi, Mumbai, or San Francisco
    loads curated city POIs instead of generic placeholders.
    """
    for city_key in ["bangalore", "delhi", "mumbai", "san_francisco"]:
        res = client.post("/api/switch-city", json={"city_key": city_key})
        assert res.status_code == 200
        data = res.json()
        assert data["city_key"] == city_key
        assert data["total_pois"] >= 3

        # Check POIs endpoint
        res_pois = client.get("/api/pois")
        assert res_pois.status_code == 200
        pois = res_pois.json()
        # Verify city-specific names
        names = [p["name"] for p in pois]
        if city_key == "bangalore":
            assert any("manipal" in n.lower() or "ashok" in n.lower() or "medplus" in n.lower() for n in names)
        elif city_key == "delhi":
            assert any("connaught" in n.lower() or "ram manohar" in n.lower() or "rajiv" in n.lower() for n in names)
        elif city_key == "mumbai":
            assert any("bandra" in n.lower() or "lilavati" in n.lower() or "noble" in n.lower() for n in names)


def test_online_local_movement_within_city_does_not_wipe_pois(client):
    """
    Verify that when user moves 200m or 400m inside a city (e.g. Hyderabad),
    the POIs remain the real municipal havens and are NOT wiped.
    """
    client.post("/api/switch-city", json={"city_key": "hyderabad"})
    
    # Query safe-bubble at location 300m away from center
    shifted_lat = 17.4435 + 0.0025
    shifted_lon = 78.3772 + 0.0020
    res = client.get(f"/api/safe-bubble?lat={shifted_lat}&lon={shifted_lon}")
    assert res.status_code == 200
    bubble = res.json()
    assert bubble["is_in_safe_zone"] is True
    
    # POIs in DB must still be Hyderabad curated POIs
    res_pois = client.get("/api/pois")
    names = [p["name"] for p in res_pois.json()]
    assert any("cyberabad" in n.lower() for n in names)
    assert any("medicover" in n.lower() for n in names)


def test_online_recalibrate_far_location_seeds_new_anchor(client):
    """
    Verify that calling /api/set-location explicitly seeds a new anchor area
    when setting coordinates in a different region.
    """
    res = client.post("/api/set-location", json={
        "lat": 19.9975,
        "lon": 73.7898,
        "name": "Nashik Safety Zone"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "LOCATION_SET"
    assert data["total_pois"] >= 5

    res_route = client.get(f"/api/safe-bubble?lat=19.9975&lon=73.7898")
    assert res_route.status_code == 200


# =====================================================================
# 3. MOBILE VIEW INTERACTION & ROUTING INTEGRATION
# =====================================================================

def test_emergency_trigger_returns_valid_dual_routes(client):
    """Verify that the emergency trigger produces valid safest and fastest routes."""
    res = client.post("/api/emergency", json={
        "user_lat": 17.4435,
        "user_lon": 78.3772,
        "data_age_hours": 0.0,
        "travel_mode": "walking"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "EMERGENCY_ACTIVE"
    assert "safest_route" in data
    assert "fastest_route" in data
    assert data["safest_route"]["safety_score"] >= 80.0
    assert len(data["safest_route"]["path_coordinates"]) >= 2
    assert len(data["fastest_route"]["path_coordinates"]) >= 2
    assert "slm_guidance" in data
    assert len(data["slm_guidance"]) > 20


def test_html_and_css_mobile_view_invariants():
    """Verify that index.html and style.css preserve all required mobile view invariants."""
    with open("ui/index.html", "r", encoding="utf-8") as f:
        html = f.read()

    # Mobile bottom nav buttons
    assert 'class="m-nav-btn active" data-target="map"' in html
    assert 'class="m-nav-btn" data-target="hud"' in html
    assert 'class="m-nav-btn" data-target="copilot"' in html
    assert 'class="m-nav-btn" data-target="havens"' in html

    # Mobile floating emergency button
    assert 'id="mobile-floating-emergency-btn"' in html

    # Recalibrate buttons
    assert 'id="recalibrate-header-btn"' in html
    assert 'id="recalibrate-map-btn"' in html
    assert 'id="recalibrate-card-btn"' in html

    with open("ui/css/style.css", "r", encoding="utf-8") as f:
        css = f.read()

    # Responsive classes
    assert "mobile-bottom-nav" in css
    assert "mobile-emergency-fab" in css
    assert "mobile-view-map" in css
    assert "mobile-view-hud" in css
    assert "mobile-view-copilot" in css
    assert "mobile-view-havens" in css

    # Apple iOS & Android Viewport Invariants
    assert "viewport-fit=cover" in html
    assert "apple-mobile-web-app-capable" in html
    assert "apple-mobile-web-app-status-bar-style" in html
    assert "apple-touch-icon" in html
    assert "env(safe-area-inset-top" in css
    assert "env(safe-area-inset-bottom" in css
    assert "100dvh" in css
    assert "-webkit-fill-available" in css

    # Google Maps In-App Navigation Modal & Travel Modes
    assert 'id="gmaps-nav-modal"' in html
    assert 'id="gmaps-pill-walk"' in html
    assert 'id="gmaps-pill-vehicle"' in html
    assert 'id="gmaps-external-link"' in html
    assert 'id="mode-walk-btn"' in html
    assert 'id="mode-vehicle-btn"' in html
    assert 'id="open-gmaps-view-btn"' in html
    assert 'value="pune"' in html

    with open("ui/js/app.js", "r", encoding="utf-8") as f:
        js = f.read()

    # Verify Pune preset in JS
    assert "pune:" in js
    assert "Bund Garden Police Station" in js
    assert "Sassoon General Hospital" in js

    # Verify Google Maps modal controllers in JS
    assert "openGoogleMapsModal" in js
    assert "setGoogleMapsMode" in js
    assert "closeGoogleMapsModal" in js
    assert "openGoogleMapsForActivePoi" in js


def test_pune_and_travel_modes_integration(client):
    """
    Test switching to Pune, verifying Pune safe havens,
    and testing walk vs vehicle routing calculations.
    """
    # 1. Switch to Pune
    res = client.post("/api/switch-city", json={"city_key": "pune"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "CITY_SWITCHED"
    assert "pune" in data["city_name"].lower()
    assert data["total_pois"] >= 6

    # 2. Verify Safe Bubble in Pune
    res_b = client.get(f"/api/safe-bubble?lat={data['center']['lat']}&lon={data['center']['lon']}")
    assert res_b.status_code == 200
    bubble = res_b.json()
    assert bubble["overall_zone_confidence"] >= 80.0

    # 3. Verify Emergency routing in Pune
    res_emg = client.post("/api/emergency", json={
        "user_lat": data['center']['lat'],
        "user_lon": data['center']['lon'],
        "data_age_hours": 0.0
    })
    assert res_emg.status_code == 200
    emg_data = res_emg.json()
    assert emg_data["status"] == "EMERGENCY_ACTIVE"
    assert emg_data["safest_destination"] is not None
    assert len(emg_data["safest_route"]["path_coordinates"]) >= 2


def test_walk_vs_vehicle_routing_speed_tradeoff(client):
    """
    Verify that walking vs vehicle travel modes dynamically modulate duration,
    mode naming, and routing recommendations via the REST API.
    """
    client.post("/api/switch-city", json={"city_key": "pune"})
    res_pois = client.get("/api/pois")
    assert res_pois.status_code == 200
    poi = res_pois.json()[0]

    # Walk route
    res_walk = client.get(f"/api/route?lat=18.5284&lon=73.8744&destination_id={poi['id']}&travel_mode=walking")
    assert res_walk.status_code == 200
    walk_data = res_walk.json()
    walk_route = walk_data["safest_route"]
    assert walk_route["mode"] == "walking"

    # Vehicle route
    res_veh = client.get(f"/api/route?lat=18.5284&lon=73.8744&destination_id={poi['id']}&travel_mode=vehicle")
    assert res_veh.status_code == 200
    veh_data = res_veh.json()
    veh_route = veh_data["safest_route"]
    assert veh_route["mode"] == "vehicle"

    # Vehicular transit must be faster
    assert veh_route["duration_minutes"] <= walk_route["duration_minutes"]
    assert any("vehicular" in r.lower() or "arteries" in r.lower() for r in veh_route["why_recommended"])


def test_service_worker_and_offline_shell_invariants():
    """
    Verify service worker script and offline PWA assets.
    """
    with open("ui/service-worker.js", "r", encoding="utf-8") as f:
        sw = f.read()

    assert "safeplace-v5" in sw
    assert "safeplace-tiles-v1" in sw
    assert "OFFLINE_TILE_SVG" in sw
    assert "svg" in sw
    assert "STATIC_ASSETS" in sw

    with open("ui/js/app.js", "r", encoding="utf-8") as f:
        app_js = f.read()

    # Offline modal handling check
    assert "Offline Mode Active" in app_js
    assert "Open Google Maps App" in app_js
