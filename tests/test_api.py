"""
Integration tests for SafePlace FastAPI REST endpoints
"""

import pytest
from fastapi.testclient import TestClient
from api.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_api_status(client):
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ONLINE_OFFLINE_READY"
    assert data["total_pois"] >= 4


def test_api_cities(client):
    res = client.get("/api/cities")
    assert res.status_code == 200
    cities = res.json()
    assert len(cities) >= 4
    city_keys = [c["key"] for c in cities]
    assert "hyderabad" in city_keys
    assert "bangalore" in city_keys


def test_api_pois(client):
    res = client.get("/api/pois")
    assert res.status_code == 200
    pois = res.json()
    assert len(pois) >= 4

    # Test filtering
    res_police = client.get("/api/pois?category=police")
    assert res_police.status_code == 200
    assert len(res_police.json()) >= 1
    assert res_police.json()[0]["category"] == "police"


def test_api_safe_bubble(client):
    res = client.get("/api/safe-bubble?lat=17.4435&lon=78.3772")
    assert res.status_code == 200
    bubble = res.json()
    assert "bands" in bubble
    assert len(bubble["bands"]) == 3
    assert bubble["overall_zone_confidence"] > 0


def test_api_route_calculation(client):
    # First get a POI id
    res_pois = client.get("/api/pois")
    poi_id = res_pois.json()[0]["id"]

    res = client.get(f"/api/route?lat=17.4435&lon=78.3772&destination_id={poi_id}")
    assert res.status_code == 200
    data = res.json()
    assert "safest_route" in data
    assert "fastest_route" in data
    assert "comparison" in data
    assert len(data["safest_route"]["path_coordinates"]) > 0


def test_api_emergency_trigger(client):
    payload = {
        "user_lat": 17.4435,
        "user_lon": 78.3772,
        "data_age_hours": 0.0
    }
    res = client.post("/api/emergency", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "EMERGENCY_ACTIVE"
    assert data["safest_destination"]["category"] in ["police", "hospital", "pharmacy", "fire_station", "public_building"]
    assert "slm_guidance" in data


def test_api_slm_chat(client):
    payload = {
        "query": "Where is the safest place I can reach?",
        "user_lat": 17.4435,
        "user_lon": 78.3772
    }
    res = client.post("/api/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "response_text" in data
    assert len(data["tool_calls"]) > 0


def test_api_city_switch(client):
    res = client.post("/api/switch-city", json={"city_key": "bangalore"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "CITY_SWITCHED"
    assert data["city_key"] == "bangalore"

    # Switch back to hyderabad
    res_back = client.post("/api/switch-city", json={"city_key": "hyderabad"})
    assert res_back.status_code == 200
