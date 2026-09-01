"""
Unit tests for Offline Spatial Database
"""

import pytest
from pathlib import Path
from core.database import OfflineDatabase, haversine_distance_meters
from data.dataset_builder import seed_offline_database


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_safeplace.db"
    db = OfflineDatabase(db_file)
    seed_offline_database(db, "hyderabad")
    return db


def test_haversine_distance():
    # Hyderabad (~111 km per degree lat)
    d = haversine_distance_meters(17.4435, 78.3772, 17.4445, 78.3772)
    assert 100.0 < d < 120.0


def test_database_pois(temp_db):
    pois = temp_db.get_all_pois()
    assert len(pois) >= 5
    police_pois = [p for p in pois if p.category == "police"]
    assert len(police_pois) >= 1
    assert police_pois[0].verification_status == "verified"


def test_database_spatial_query(temp_db):
    # Search around Hyderabad HITEC City anchor (17.4435, 78.3772) within 1500m
    nearby = temp_db.get_nearby_pois(17.4435, 78.3772, max_distance_meters=1500.0)
    assert len(nearby) > 0
    # Nearest should have lowest distance
    for i in range(len(nearby) - 1):
        assert nearby[i][1] <= nearby[i + 1][1]


def test_database_road_segments(temp_db):
    segments = temp_db.get_all_road_segments()
    assert len(segments) >= 5
    alleys = [s for s in segments if s.road_type == "alley"]
    assert len(alleys) >= 1
    assert alleys[0].lighting < 0.3  # Dark alley
