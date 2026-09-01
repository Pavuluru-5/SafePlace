"""
Unit tests for Safety Risk Engine
"""

import pytest
from core.database import OfflineDatabase
from core.risk_engine import SafetyRiskEngine
from data.dataset_builder import seed_offline_database


@pytest.fixture
def risk_env(tmp_path):
    db_file = tmp_path / "test_risk.db"
    db = OfflineDatabase(db_file)
    seed_offline_database(db, "hyderabad")
    engine = SafetyRiskEngine(db)
    return db, engine


def test_poi_safety_scoring(risk_env):
    db, engine = risk_env
    police = db.get_poi_by_id("HYD_POLICE_01")
    assert police is not None

    score = engine.evaluate_poi_safety(police, 17.4435, 78.3772)
    assert 80.0 <= score.safety_score <= 100.0
    assert score.risk_score == round(100.0 - score.safety_score, 1)
    assert "infrastructure" in score.breakdown
    assert score.breakdown["emergency_proximity"] >= 95.0


def test_segment_safety_comparison(risk_env):
    db, engine = risk_env
    segments = db.get_all_road_segments()
    
    grand_blvd = next(s for s in segments if s.id == "HYD_SEG_01")
    dark_alley = next(s for s in segments if s.id == "HYD_SEG_03")

    grand_score = engine.evaluate_segment_safety(grand_blvd)
    alley_score = engine.evaluate_segment_safety(dark_alley)

    assert grand_score > 75.0
    assert alley_score < 50.0
    assert grand_score > alley_score  # Illuminated boulevard is significantly safer than unlit alley
