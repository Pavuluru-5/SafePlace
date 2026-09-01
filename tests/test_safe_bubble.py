"""
Unit tests for Dynamic Safe Bubble Monitor
"""

import pytest
from core.database import OfflineDatabase
from core.risk_engine import SafetyRiskEngine
from core.confidence_engine import ConfidenceEngine
from core.safe_bubble import SafeBubbleMonitor
from data.dataset_builder import seed_offline_database


@pytest.fixture
def bubble_env(tmp_path):
    db_file = tmp_path / "test_bubble.db"
    db = OfflineDatabase(db_file)
    seed_offline_database(db, "hyderabad")
    risk_eng = SafetyRiskEngine(db)
    conf_eng = ConfidenceEngine()
    monitor = SafeBubbleMonitor(db, risk_eng, conf_eng)
    return db, monitor


def test_safe_bubble_calculation(bubble_env):
    db, monitor = bubble_env
    user_lat, user_lon = 17.4435, 78.3772

    result = monitor.calculate_safe_bubble(user_lat, user_lon, travel_mode="walking")

    assert len(result.bands) == 3
    assert result.bands[0].minutes == 5
    assert result.bands[1].minutes == 10
    assert result.bands[2].minutes == 15

    # Band 2 (10 min) should contain at least as many or more destinations than Band 1 (5 min)
    assert len(result.bands[1].destinations) >= len(result.bands[0].destinations)
    assert len(result.bands[2].destinations) >= len(result.bands[1].destinations)

    assert result.recommended_destination is not None
    assert result.overall_zone_confidence > 0
    assert result.is_in_safe_zone is True
