"""
Unit tests for On-Device SLM Copilot and Responsible AI Guardrails
"""

import pytest
from core.database import OfflineDatabase
from core.risk_engine import SafetyRiskEngine
from core.confidence_engine import ConfidenceEngine
from core.route_engine import SafeRouteEngine
from core.safe_bubble import SafeBubbleMonitor
from core.slm_engine import OnDeviceSLMCopilot
from data.dataset_builder import seed_offline_database


@pytest.fixture
def copilot_env(tmp_path):
    db_file = tmp_path / "test_slm.db"
    db = OfflineDatabase(db_file)
    seed_offline_database(db, "hyderabad")
    risk_eng = SafetyRiskEngine(db)
    conf_eng = ConfidenceEngine()
    route_eng = SafeRouteEngine(db, risk_eng, conf_eng)
    bubble_mon = SafeBubbleMonitor(db, risk_eng, conf_eng)
    copilot = OnDeviceSLMCopilot(db, risk_eng, conf_eng, route_eng, bubble_mon)
    return copilot


def test_slm_recommendation_fresh_data(copilot_env):
    user_lat, user_lon = 17.4435, 78.3772
    resp = copilot_env.process_query(
        query="Where is the safest place I can go right now?",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )

    assert resp.abstained is False
    assert resp.confidence_tier == "HIGH"
    assert len(resp.tool_calls) >= 2
    assert "recommend" in resp.response_text.lower()
    assert resp.suggested_poi is not None
    assert resp.suggested_route is not None


def test_slm_abstention_on_stale_data(copilot_env):
    user_lat, user_lon = 17.4435, 78.3772
    # Simulate data that is 700 hours (~1 month) old
    resp = copilot_env.process_query(
        query="Where is the safest place I can go right now?",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=700.0
    )

    assert resp.abstained is True
    assert resp.confidence_tier == "UNKNOWN"
    assert "don't have enough recent information" in resp.response_text.lower() or "abstain" in resp.response_text.lower()
    assert "reason_for_abstention" in resp.evidence_grounding


def test_slm_why_explanation_intent(copilot_env):
    user_lat, user_lon = 17.4435, 78.3772
    resp = copilot_env.process_query(
        query="Why did you choose this route?",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=2.0
    )

    assert resp.abstained is False
    assert "infrastructure" in resp.response_text.lower()
    assert "lighting" in resp.response_text.lower()


def test_slm_hospital_search_intent(copilot_env):
    user_lat, user_lon = 17.4435, 78.3772
    resp = copilot_env.process_query(
        query="Find the nearest hospital for trauma care",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )

    assert resp.abstained is False
    assert resp.suggested_poi is not None
    assert resp.suggested_poi.category == "hospital"
    assert "medicover" in resp.suggested_poi.name.lower() or "hospital" in resp.suggested_poi.name.lower()
    assert "hospital" in resp.response_text.lower()


def test_slm_pharmacy_search_intent(copilot_env):
    user_lat, user_lon = 17.4435, 78.3772
    resp = copilot_env.process_query(
        query="Where can I find a 24/7 pharmacy or chemist?",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )

    assert resp.abstained is False
    assert resp.suggested_poi is not None
    assert resp.suggested_poi.category == "pharmacy"
    assert "pharmacy" in resp.response_text.lower()


def test_slm_route_comparison_intent(copilot_env):
    user_lat, user_lon = 17.4435, 78.3772
    resp = copilot_env.process_query(
        query="Compare the fastest route and safest route",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )

    assert resp.abstained is False
    assert "safest route" in resp.response_text.lower()
    assert "fastest route" in resp.response_text.lower()


def test_slm_emergency_intent(copilot_env):
    user_lat, user_lon = 17.4435, 78.3772
    resp = copilot_env.process_query(
        query="I'm in danger! Help me immediately",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )

    assert resp.abstained is False
    assert "emergency" in resp.response_text.lower()
    assert resp.suggested_poi is not None


def test_slm_greeting_intent(copilot_env):
    user_lat, user_lon = 17.4435, 78.3772
    resp = copilot_env.process_query(
        query="Hello, how are you?",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )

    assert resp.abstained is False
    assert "safeplace" in resp.response_text.lower()

