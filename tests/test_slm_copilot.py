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


def test_slm_typo_resilience(copilot_env):
    user_lat, user_lon = 17.4435, 78.3772
    
    # Misspelled "hosptal"
    resp_hosp = copilot_env.process_query(
        query="Where is the nearest hosptal?",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )
    assert resp_hosp.suggested_poi is not None
    assert resp_hosp.suggested_poi.category == "hospital"
    assert "hospital" in resp_hosp.response_text.lower()

    # Misspelled "polce"
    resp_pol = copilot_env.process_query(
        query="find me the polce station",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )
    assert resp_pol.suggested_poi is not None
    assert resp_pol.suggested_poi.category == "police"

    # Misspelled "pharmaxy"
    resp_pharm = copilot_env.process_query(
        query="I need a 24/7 pharmaxy",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )
    assert resp_pharm.suggested_poi is not None
    assert resp_pharm.suggested_poi.category == "pharmacy"


def test_slm_out_of_domain_guardrail(copilot_env):
    user_lat, user_lon = 17.4435, 78.3772

    # Joke query
    resp_joke = copilot_env.process_query(
        query="Tell me a funny joke",
        user_lat=user_lat,
        user_lon=user_lon
    )
    assert resp_joke.suggested_poi is None
    assert resp_joke.suggested_route is None
    assert "dedicated exclusively to personal safety" in resp_joke.response_text
    assert resp_joke.evidence_grounding.get("query_classified_as") == "out_of_domain"

    # Trivia query
    resp_trivia = copilot_env.process_query(
        query="What is the capital of France?",
        user_lat=user_lat,
        user_lon=user_lon
    )
    assert resp_trivia.suggested_poi is None
    assert resp_trivia.suggested_route is None
    assert "dedicated exclusively to personal safety" in resp_trivia.response_text

    # Coding query
    resp_code = copilot_env.process_query(
        query="Write Python code to reverse a linked list",
        user_lat=user_lat,
        user_lon=user_lon
    )
    assert resp_code.suggested_poi is None
    assert resp_code.suggested_route is None


def test_slm_informal_safety_and_distress_phrasing(copilot_env):
    user_lat, user_lon = 17.4435, 78.3772

    # Colloquial distress: "jittery", "creeping behind me"
    resp_distress = copilot_env.process_query(
        query="I feel jittery and someone is creeping behind me",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )
    assert resp_distress.suggested_poi is not None
    assert "emergency guidance active" in resp_distress.response_text.lower()

    # Colloquial pharmacy: "bandages"
    resp_pharm = copilot_env.process_query(
        query="Where can I get bandages and antiseptic right now?",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )
    assert resp_pharm.suggested_poi is not None
    assert resp_pharm.suggested_poi.category == "pharmacy"

    # Colloquial medical: "physician", "bleeding"
    resp_doc = copilot_env.process_query(
        query="I need an emergency physician for severe bleeding",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )
    assert resp_doc.suggested_poi is not None
    assert resp_doc.suggested_poi.category == "hospital"

    # Colloquial lighting / route comparison: "more street lights"
    resp_lights = copilot_env.process_query(
        query="Which way has more street lights and fewer dark alleys?",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )
    assert "safest route" in resp_lights.response_text.lower()
    assert "fastest route" in resp_lights.response_text.lower()


def test_slm_follow_up_chips_generation(copilot_env):
    user_lat, user_lon = 17.4435, 78.3772

    # Query 1: Greeting
    resp_greet = copilot_env.process_query("Hello there", user_lat, user_lon)
    assert len(resp_greet.follow_up_chips) >= 2
    assert any("hospital" in c.lower() or "safe" in c.lower() for c in resp_greet.follow_up_chips)

    # Query 2: Hospital search
    resp_hosp = copilot_env.process_query("Where is the nearest hospital?", user_lat, user_lon, age_hours_override=1.0)
    assert len(resp_hosp.follow_up_chips) >= 2
    assert any("compare" in c.lower() or "why" in c.lower() or "open" in c.lower() for c in resp_hosp.follow_up_chips)

    # Query 3: Route comparison
    resp_comp = copilot_env.process_query("Compare the fastest and safest routes", user_lat, user_lon, age_hours_override=1.0)
    assert len(resp_comp.follow_up_chips) >= 2

    # Query 4: Distress / Emergency
    resp_distress = copilot_env.process_query("I'm not safe, emergency", user_lat, user_lon, age_hours_override=1.0)
    assert len(resp_distress.follow_up_chips) >= 2
    assert any("112" in c or "call" in c.lower() for c in resp_distress.follow_up_chips)


def test_slm_multi_turn_conversational_memory(copilot_env):
    user_lat, user_lon = 17.4435, 78.3772

    # Turn 1: Locate nearest hospital
    turn1 = copilot_env.process_query(
        query="Where is the nearest hospital?",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )
    assert turn1.suggested_poi is not None
    hospital_name = turn1.suggested_poi.name

    # Turn 2: Follow-up asking "Is it open right now?" (Pronoun 'it', no facility name mentioned)
    turn2 = copilot_env.process_query(
        query="Is it open right now?",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )
    assert turn2.suggested_poi is not None
    assert turn2.suggested_poi.name == hospital_name
    assert "operating hours" in turn2.response_text.lower()
    assert turn1.suggested_poi.opening_hours in turn2.response_text

    # Turn 3: Follow-up asking "What is their phone number?" (Pronoun 'their', no facility name)
    turn3 = copilot_env.process_query(
        query="What is their phone number?",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )
    assert turn3.suggested_poi is not None
    assert turn3.suggested_poi.name == hospital_name
    assert "contact details" in turn3.response_text.lower() or "telephone" in turn3.response_text.lower()
    if turn1.suggested_poi.phone:
        assert turn1.suggested_poi.phone in turn3.response_text

    # Turn 4: Follow-up asking "Why did you choose this route?"
    turn4 = copilot_env.process_query(
        query="Why did you choose this route?",
        user_lat=user_lat,
        user_lon=user_lon,
        age_hours_override=1.0
    )
    assert turn4.suggested_poi is not None
    assert turn4.suggested_poi.name == hospital_name
    assert "safest route" in turn4.response_text.lower()


