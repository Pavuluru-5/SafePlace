"""
Unit and integration tests for Dynamic Location and Safe Havens Auto-Centering
"""
import pytest
from fastapi.testclient import TestClient
from api.server import app

@pytest.fixture
def client():
    return TestClient(app)

def test_dynamic_location_seeding(client):
    payload = {
        "lat": 18.5204,
        "lon": 73.8567,
        "name": "Pune City Center"
    }
    res = client.post("/api/set-location", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "LOCATION_SET"
    assert data["total_pois"] == 6
    assert data["total_segments"] >= 5

    res_pois = client.get("/api/pois?lat=18.5204&lon=73.8567")
    assert res_pois.status_code == 200
    pois = res_pois.json()
    assert len(pois) == 6
    categories = [p["category"] for p in pois]
    assert "police" in categories
    assert "hospital" in categories
    assert "pharmacy" in categories
    assert "transport_hub" in categories
    assert "fire_station" in categories

def test_dynamic_safe_bubble_calculation(client):
    res = client.get("/api/safe-bubble?lat=18.5204&lon=73.8567")
    assert res.status_code == 200
    bubble = res.json()
    assert bubble["is_in_safe_zone"] is True
    assert len(bubble["bands"]) == 3
    b10_count = len(bubble["bands"][1]["destinations"])
    assert b10_count >= 1

def test_dynamic_emergency_trigger(client):
    payload = {
        "user_lat": 18.5204,
        "user_lon": 73.8567,
        "data_age_hours": 0.0
    }
    res = client.post("/api/emergency", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "EMERGENCY_ACTIVE"
    assert data["safest_destination"] is not None
    assert "safest_route" in data
    assert len(data["safest_route"]["path_coordinates"]) >= 2

def test_dynamic_slm_chat_at_custom_location(client):
    payload = {
        "query": "Where is the nearest hospital?",
        "user_lat": 18.5204,
        "user_lon": 73.8567
    }
    res = client.post("/api/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "hospital" in data["response_text"].lower()
    assert data["tool_calls"] is not None
