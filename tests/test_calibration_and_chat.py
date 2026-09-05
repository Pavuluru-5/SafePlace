"""
Tests for Safe Havens Spatial Calibration, Chatbot Dialogue Transitions, and Dynamic Wayfinding
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
from data.dataset_builder import seed_offline_database


@pytest.fixture
def test_env(tmp_path):
    db_file = tmp_path / "test_calib.db"
    db = OfflineDatabase(db_file)
    seed_offline_database(db, "hyderabad")
    risk_eng = SafetyRiskEngine(db)
    conf_eng = ConfidenceEngine()
    route_eng = SafeRouteEngine(db, risk_eng, conf_eng)
    bubble_mon = SafeBubbleMonitor(db, risk_eng, conf_eng)
    copilot = OnDeviceSLMCopilot(db, risk_eng, conf_eng, route_eng, bubble_mon)
    return {
        "db": db,
        "risk_eng": risk_eng,
        "conf_eng": conf_eng,
        "route_eng": route_eng,
        "bubble_mon": bubble_mon,
        "copilot": copilot
    }


@pytest.fixture
def client():
    return TestClient(app)


def test_spatial_haven_calibration_on_movement(test_env):
    """
    Verify that when the user moves closer to a safe haven (e.g. Medicover Hospital),
    the calculated distance decreases and the safe haven is dynamically promoted into
    a closer isochrone band (5-min band).
    """
    db = test_env["db"]
    bubble_mon = test_env["bubble_mon"]
    pois = db.get_all_pois()
    
    medicover = next((p for p in pois if "medicover" in p.name.lower()), pois[0])
    
    # Point A: User at HITEC City center (17.4435, 78.3772)
    start_lat, start_lon = 17.4435, 78.3772
    dist_start = haversine_distance_meters(start_lat, start_lon, medicover.lat, medicover.lon)
    bubble_start = bubble_mon.calculate_safe_bubble(start_lat, start_lon)
    
    # Point B: User moves directly closer to Medicover Hospital (e.g., 80m away)
    close_lat = medicover.lat + 0.0005
    close_lon = medicover.lon + 0.0005
    dist_close = haversine_distance_meters(close_lat, close_lon, medicover.lat, medicover.lon)
    bubble_close = bubble_mon.calculate_safe_bubble(close_lat, close_lon)
    
    # Verify distance decreased
    assert dist_close < dist_start
    assert dist_close < 150  # Very close
    
    # Verify that Medicover is in the 5-min band (<= 450m) at the closer point
    b5_dest_ids = [d["poi"].id for d in bubble_close.bands[0].destinations]
    assert medicover.id in b5_dest_ids


def test_chatbot_smooth_dialogue_transition_distance_then_greeting(test_env):
    """
    Test user flow:
    1. User asks distance question: "How far is Medicover Hospital?"
    2. User follows up with greeting: "Hello, how are you?"
    3. User follows up with pleasantry: "Thank you!"
    Verify that greeting & pleasantry transition smoothly WITHOUT forcing route recommendations.
    """
    copilot = test_env["copilot"]
    user_lat, user_lon = 17.4435, 78.3772

    # Step 1: Distance question
    resp_dist = copilot.process_query(
        query="How far is the Medicover Hospital?",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )
    assert resp_dist.abstained is False
    assert "distance" in resp_dist.response_text.lower() or "meters" in resp_dist.response_text.lower()
    assert resp_dist.suggested_poi is not None
    assert "medicover" in resp_dist.suggested_poi.name.lower() or resp_dist.suggested_poi.category == "hospital"

    # Step 2: Next question is greeting
    resp_greet = copilot.process_query(
        query="Hello, how are you?",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )
    assert resp_greet.abstained is False
    assert "safeplace" in resp_greet.response_text.lower()
    assert "safe bubble" in resp_greet.response_text.lower()
    # Ensure greeting does NOT override with a forced route recommendation
    assert resp_greet.suggested_route is None

    # Step 3: Next question is pleasantry
    resp_thanks = copilot.process_query(
        query="Thank you so much!",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )
    assert resp_thanks.abstained is False
    assert "welcome" in resp_thanks.response_text.lower()
    assert resp_thanks.suggested_route is None


def test_recalibrate_safe_havens_endpoint(client):
    """
    Test explicit recalibration via /api/set-location.
    Verifies that safehavens are seeded around the requested new coordinates.
    """
    new_lat, new_lon = 13.0827, 80.2707  # Chennai Central coordinates
    payload = {
        "lat": new_lat,
        "lon": new_lon,
        "name": "Chennai Refuge Hub"
    }
    res = client.post("/api/set-location", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "LOCATION_SET"
    assert data["total_pois"] >= 5
    assert len(data["pois"]) >= 5

    # Safe bubble should now be calibrated around Chennai
    res_bubble = client.get(f"/api/safe-bubble?lat={new_lat}&lon={new_lon}")
    assert res_bubble.status_code == 200
    bubble = res_bubble.json()
    assert bubble["is_in_safe_zone"] is True
    assert len(bubble["bands"]) == 3
