"""
Unit tests for Confidence & Data Trust Engine and 'I Don't Know' Abstention
"""

import pytest
from datetime import datetime, timedelta
from core.models import POI
from core.confidence_engine import ConfidenceEngine
import config


@pytest.fixture
def confidence_engine():
    return ConfidenceEngine()


def test_fresh_data_high_confidence(confidence_engine):
    poi = POI(
        id="TEST_POI_01",
        name="Precinct 1",
        category="police",
        lat=37.7785,
        lon=-122.4150,
        opening_hours="24/7",
        accessibility="full",
        verification_status="verified",
        source="Police_Department_Feed",
        last_updated=datetime.now().isoformat(),
        confidence=98.0
    )

    conf = confidence_engine.evaluate_poi_confidence(poi, age_hours_override=2.0)
    assert conf.score >= config.CONFIDENCE_THRESHOLDS["HIGH"]
    assert conf.tier == "HIGH"
    assert not conf.abstained


def test_stale_data_triggers_abstention(confidence_engine):
    # Data is 600 hours (~25 days) or 1000 hours old
    poi = POI(
        id="TEST_POI_OLD",
        name="Old Dispensary",
        category="pharmacy",
        lat=37.7745,
        lon=-122.4180,
        opening_hours="24/7",
        accessibility="full",
        verification_status="provisional",
        source="Crowdsourced_Community",
        last_updated=(datetime.now() - timedelta(days=40)).isoformat(),
        confidence=60.0
    )

    conf = confidence_engine.evaluate_poi_confidence(poi, age_hours_override=800.0)
    assert conf.score < config.CONFIDENCE_THRESHOLDS["ABSTAIN"]
    assert conf.tier == "UNKNOWN"
    assert conf.abstained is True
    assert "UNKNOWN / ABSTAIN" in conf.explanation
