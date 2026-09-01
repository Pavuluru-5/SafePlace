"""
Unit tests for Safe Route Graph Engine (Safest vs Fastest Route)
"""

import pytest
from core.database import OfflineDatabase
from core.risk_engine import SafetyRiskEngine
from core.confidence_engine import ConfidenceEngine
from core.route_engine import SafeRouteEngine
from data.dataset_builder import seed_offline_database


@pytest.fixture
def route_env(tmp_path):
    db_file = tmp_path / "test_route.db"
    db = OfflineDatabase(db_file)
    seed_offline_database(db, "hyderabad")
    risk_eng = SafetyRiskEngine(db)
    conf_eng = ConfidenceEngine()
    route_eng = SafeRouteEngine(db, risk_eng, conf_eng)
    return db, route_eng


def test_safest_vs_fastest_route_tradeoff(route_env):
    db, route_eng = route_env
    
    # Destination: Cyberabad Police Station
    # Start: User at N1 (17.4435, 78.3772)
    police = db.get_poi_by_id("HYD_POLICE_01")
    assert police is not None

    safest, fastest = route_eng.calculate_routes_to_destination(
        user_lat=17.4435,
        user_lon=78.3772,
        destination=police
    )

    assert safest.is_safest is True
    assert fastest.is_fastest is True

    # Safest route should have higher or equal safety score
    assert safest.safety_score >= fastest.safety_score
    # Safest route should have superior or equal lighting coverage
    assert safest.lighting_percentage >= fastest.lighting_percentage
    # Fastest route should have shorter or equal travel time
    assert fastest.duration_minutes <= safest.duration_minutes

    # Ensure steps and "why recommended" are populated
    assert len(safest.steps) > 0
    assert len(safest.why_recommended) > 0
