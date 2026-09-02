"""
SafePlace Offline Spatial Database Manager
Uses SQLite with local indexing and Haversine geospatial calculations.
Compliant with Section 8 & Appendix A.
"""

import sqlite3
import json
import math
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from core.models import POI, RoadSegment, IncidentAggregate
import config


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in meters."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class OfflineDatabase:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.DATABASE_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # POIs Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pois (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    opening_hours TEXT DEFAULT '24/7',
                    accessibility TEXT DEFAULT 'full',
                    verification_status TEXT DEFAULT 'verified',
                    source TEXT DEFAULT 'Municipal_GIS',
                    last_updated TEXT NOT NULL,
                    confidence REAL DEFAULT 85.0,
                    phone TEXT,
                    address TEXT,
                    capacity_level TEXT DEFAULT 'normal'
                )
            """)

            # Road Segments Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS road_segments (
                    id TEXT PRIMARY KEY,
                    u_node TEXT NOT NULL,
                    v_node TEXT NOT NULL,
                    name TEXT NOT NULL,
                    road_type TEXT NOT NULL,
                    geometry_json TEXT NOT NULL,
                    length_meters REAL NOT NULL,
                    lighting REAL DEFAULT 0.8,
                    footpath INTEGER DEFAULT 1,
                    activity_proxy REAL DEFAULT 0.7,
                    cctv_available INTEGER DEFAULT 0,
                    incident_density REAL DEFAULT 0.1,
                    speed_kmh REAL DEFAULT 4.5,
                    last_updated TEXT NOT NULL,
                    confidence REAL DEFAULT 90.0
                )
            """)

            # Incident Aggregates Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS incident_aggregates (
                    id TEXT PRIMARY KEY,
                    area_grid TEXT NOT NULL,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    radius_meters REAL DEFAULT 300.0,
                    time_bucket TEXT DEFAULT 'all',
                    category TEXT NOT NULL,
                    severity REAL NOT NULL,
                    count INTEGER NOT NULL,
                    source TEXT DEFAULT 'Aggregated_Records',
                    confidence REAL DEFAULT 80.0,
                    last_updated TEXT NOT NULL
                )
            """)

            # Sync Package Metadata Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_packages (
                    version TEXT PRIMARY KEY,
                    map_version TEXT NOT NULL,
                    safety_version TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT
                )
            """)

            # Spatial Indices for Fast Local Querying
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_poi_category ON pois(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_poi_coords ON pois(lat, lon)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_road_nodes ON road_segments(u_node, v_node)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_incident_coords ON incident_aggregates(lat, lon)")

            conn.commit()

    def clear_all(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pois")
            cursor.execute("DELETE FROM road_segments")
            cursor.execute("DELETE FROM incident_aggregates")
            conn.commit()

    def insert_pois_batch(self, pois: List[POI]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR REPLACE INTO pois 
                (id, name, category, lat, lon, opening_hours, accessibility, 
                 verification_status, source, last_updated, confidence, phone, address, capacity_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    p.id, p.name, p.category, p.lat, p.lon,
                    p.opening_hours, p.accessibility, p.verification_status,
                    p.source, p.last_updated, p.confidence, p.phone, p.address, p.capacity_level
                )
                for p in pois
            ])
            conn.commit()

    def insert_segments_batch(self, segments: List[RoadSegment]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR REPLACE INTO road_segments
                (id, u_node, v_node, name, road_type, geometry_json, length_meters, 
                 lighting, footpath, activity_proxy, cctv_available, incident_density, 
                 speed_kmh, last_updated, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    s.id, s.u_node, s.v_node, s.name, s.road_type,
                    json.dumps(s.geometry), s.length_meters, s.lighting,
                    1 if s.footpath else 0, s.activity_proxy, 1 if s.cctv_available else 0,
                    s.incident_density, s.speed_kmh, s.last_updated, s.confidence
                )
                for s in segments
            ])
            conn.commit()

    def insert_incidents_batch(self, incidents: List[IncidentAggregate]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR REPLACE INTO incident_aggregates
                (id, area_grid, lat, lon, radius_meters, time_bucket, category, severity, count, source, confidence, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    i.id, i.area_grid, i.lat, i.lon, i.radius_meters,
                    i.time_bucket, i.category, i.severity, i.count,
                    i.source, i.confidence, i.last_updated
                )
                for i in incidents
            ])
            conn.commit()

    def insert_poi(self, poi: POI):
        self.insert_pois_batch([poi])

    def insert_road_segment(self, segment: RoadSegment):
        self.insert_segments_batch([segment])

    def insert_incident_aggregate(self, incident: IncidentAggregate):
        self.insert_incidents_batch([incident])

    def get_all_pois(self) -> List[POI]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pois")
            rows = cursor.fetchall()
            return [
                POI(
                    id=r["id"], name=r["name"], category=r["category"],
                    lat=r["lat"], lon=r["lon"], opening_hours=r["opening_hours"],
                    accessibility=r["accessibility"], verification_status=r["verification_status"],
                    source=r["source"], last_updated=r["last_updated"], confidence=r["confidence"],
                    phone=r["phone"], address=r["address"], capacity_level=r["capacity_level"]
                )
                for r in rows
            ]

    def get_poi_by_id(self, poi_id: str) -> Optional[POI]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pois WHERE id = ?", (poi_id,))
            r = cursor.fetchone()
            if not r:
                return None
            return POI(
                id=r["id"], name=r["name"], category=r["category"],
                lat=r["lat"], lon=r["lon"], opening_hours=r["opening_hours"],
                accessibility=r["accessibility"], verification_status=r["verification_status"],
                source=r["source"], last_updated=r["last_updated"], confidence=r["confidence"],
                phone=r["phone"], address=r["address"], capacity_level=r["capacity_level"]
            )

    def get_nearby_pois(self, lat: float, lon: float, max_distance_meters: float = 3000.0, 
                        category: Optional[str] = None, limit: int = 20) -> List[Tuple[POI, float]]:
        """
        Retrieves POIs within max_distance_meters, sorted by proximity.
        Returns list of (POI, distance_meters).
        """
        all_pois = self.get_all_pois()
        results = []
        for p in all_pois:
            if category and p.category.lower() != category.lower():
                continue
            dist = haversine_distance_meters(lat, lon, p.lat, p.lon)
            if dist <= max_distance_meters:
                results.append((p, dist))
        
        results.sort(key=lambda x: x[1])
        return results[:limit]

    def get_all_road_segments(self) -> List[RoadSegment]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM road_segments")
            rows = cursor.fetchall()
            return [
                RoadSegment(
                    id=r["id"], u_node=r["u_node"], v_node=r["v_node"],
                    name=r["name"], road_type=r["road_type"],
                    geometry=json.loads(r["geometry_json"]),
                    length_meters=r["length_meters"], lighting=r["lighting"],
                    footpath=bool(r["footpath"]), activity_proxy=r["activity_proxy"],
                    cctv_available=bool(r["cctv_available"]),
                    incident_density=r["incident_density"],
                    speed_kmh=r["speed_kmh"], last_updated=r["last_updated"],
                    confidence=r["confidence"]
                )
                for r in rows
            ]

    def get_all_incident_aggregates(self) -> List[IncidentAggregate]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM incident_aggregates")
            rows = cursor.fetchall()
            return [
                IncidentAggregate(
                    id=r["id"], area_grid=r["area_grid"], lat=r["lat"], lon=r["lon"],
                    radius_meters=r["radius_meters"], time_bucket=r["time_bucket"],
                    category=r["category"], severity=r["severity"], count=r["count"],
                    source=r["source"], confidence=r["confidence"], last_updated=r["last_updated"]
                )
                for r in rows
            ]

    def get_incidents_near_point(self, lat: float, lon: float, radius_meters: float = 500.0) -> List[IncidentAggregate]:
        incidents = self.get_all_incident_aggregates()
        near = []
        for inc in incidents:
            dist = haversine_distance_meters(lat, lon, inc.lat, inc.lon)
            if dist <= (radius_meters + inc.radius_meters):
                near.append(inc)
        return near

    def set_global_data_age_hours(self, hours_old: float):
        """
        Simulates data aging for demonstration and test purposes.
        Updates all timestamps to (now - hours_old).
        """
        simulated_time = (datetime.now() - timedelta(hours=hours_old)).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE pois SET last_updated = ?", (simulated_time,))
            cursor.execute("UPDATE road_segments SET last_updated = ?", (simulated_time,))
            cursor.execute("UPDATE incident_aggregates SET last_updated = ?", (simulated_time,))
            conn.commit()
