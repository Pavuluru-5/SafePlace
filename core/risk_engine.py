"""
SafePlace Safety Risk Engine
Computes multi-factor safety & risk scores (0-100) for destinations and road corridors.
Compliant with Section 10 & Section 30.
"""

from typing import Dict, List, Optional, Any, Tuple
from core.models import POI, RoadSegment, IncidentAggregate, SafetyScore
from core.database import OfflineDatabase, haversine_distance_meters
import config


class SafetyRiskEngine:
    def __init__(self, db: OfflineDatabase, weights: Optional[Dict[str, float]] = None):
        self.db = db
        self.weights = weights or config.RISK_WEIGHTS

    def evaluate_poi_safety(self, poi: POI, user_lat: float, user_lon: float,
                            age_hours_override: Optional[float] = None) -> SafetyScore:
        """
        Evaluates the safety score of a candidate destination POI.
        Scores from 0 (very high risk) to 100 (safest reachable haven).
        """
        dist_meters = haversine_distance_meters(user_lat, user_lon, poi.lat, poi.lon)

        # 1. Infrastructure & Facility Category (Weight 25%)
        # Police and Hospitals are inherently secure hubs with on-duty personnel
        cat_scores = {
            "police": 100.0,
            "hospital": 95.0,
            "fire_station": 90.0,
            "pharmacy": 82.0,
            "public_building": 80.0,
            "transport_hub": 75.0,
            "hotel": 72.0,
            "shelter": 85.0
        }
        category_score = cat_scores.get(poi.category.lower(), 65.0)

        # 2. Emergency Service Proximity / In-Facility Security (Weight 20%)
        # If POI is itself an emergency facility or near one
        if poi.category.lower() in ["police", "hospital", "fire_station"]:
            emergency_proximity = 100.0
        else:
            # Find closest police/hospital to this POI
            nearby_emergency = self.db.get_nearby_pois(poi.lat, poi.lon, max_distance_meters=2000.0)
            emergency_pois = [p for p, d in nearby_emergency if p.category in ["police", "hospital"]]
            if emergency_pois:
                closest_d = min(d for p, d in nearby_emergency if p.category in ["police", "hospital"])
                emergency_proximity = max(20.0, 100.0 - (closest_d / 20.0))
            else:
                emergency_proximity = 40.0

        # 3. Activity / Public Place Proxy (Weight 15%)
        # Open 24/7, high staffing, verified commercial / government hub
        is_24_7 = "24" in poi.opening_hours or "always" in poi.opening_hours.lower()
        activity_proxy = 95.0 if is_24_7 else 75.0

        # 4. Historical Incident Density Around POI (Weight 15%)
        nearby_incidents = self.db.get_incidents_near_point(poi.lat, poi.lon, radius_meters=400.0)
        if not nearby_incidents:
            incident_score = 95.0
        else:
            total_severity = sum(inc.severity * inc.count for inc in nearby_incidents)
            incident_score = max(10.0, 100.0 - (total_severity * 8.0))

        # 5. Lighting / Environmental Visibility (Weight 10%)
        lighting_score = 90.0 if poi.category in ["police", "hospital", "transport_hub"] else 80.0

        # 6. Accessibility & Operational Status (Weight 10%)
        accessibility_score = 95.0 if "full" in poi.accessibility.lower() else 75.0

        # 7. Data Freshness Factor (Weight 5%)
        # Handled as an input feature for risk calculation
        freshness_score = 90.0 if (age_hours_override is None or age_hours_override < 48) else max(20.0, 100.0 - (age_hours_override / 10.0))

        # Calculate Weighted Safety Score
        total_safety = (
            category_score * self.weights["infrastructure"] +
            emergency_proximity * self.weights["emergency_proximity"] +
            activity_proxy * self.weights["activity_proxy"] +
            incident_score * self.weights["incident_pattern"] +
            lighting_score * self.weights["lighting"] +
            accessibility_score * self.weights["accessibility"] +
            freshness_score * self.weights["data_freshness"]
        )

        total_safety = max(0.0, min(100.0, total_safety))
        risk_score = 100.0 - total_safety

        breakdown = {
            "infrastructure": round(category_score, 1),
            "emergency_proximity": round(emergency_proximity, 1),
            "activity_proxy": round(activity_proxy, 1),
            "incident_pattern": round(incident_score, 1),
            "lighting": round(lighting_score, 1),
            "accessibility": round(accessibility_score, 1),
            "data_freshness": round(freshness_score, 1)
        }

        return SafetyScore(
            entity_id=poi.id,
            entity_type="poi",
            safety_score=round(total_safety, 1),
            risk_score=round(risk_score, 1),
            breakdown=breakdown,
            calculated_at="now",
            model_version="RiskModel_v1.0"
        )

    def evaluate_segment_safety(self, segment: RoadSegment) -> float:
        """
        Computes safety score (0-100) for a single road segment.
        Used for edge weights in graph routing.
        """
        # Infrastructure score based on road type
        road_type_scores = {
            "primary": 90.0,
            "secondary": 85.0,
            "residential": 75.0,
            "footway": 70.0,
            "alley": 35.0
        }
        infra = road_type_scores.get(segment.road_type.lower(), 65.0)

        # Lighting (0.0 to 1.0 -> 0 to 100)
        lighting = segment.lighting * 100.0

        # Footpath presence
        footpath = 95.0 if segment.footpath else 40.0

        # Activity proxy (0.0 to 1.0 -> 0 to 100)
        activity = segment.activity_proxy * 100.0

        # Incident penalty
        incident_safety = max(10.0, 100.0 - (segment.incident_density * 90.0))

        # CCTV bonus
        cctv_bonus = 10.0 if segment.cctv_available else 0.0

        # Segment Safety Score
        seg_score = (
            infra * 0.25 +
            lighting * 0.25 +
            footpath * 0.15 +
            activity * 0.15 +
            incident_safety * 0.20 +
            cctv_bonus
        )
        return max(10.0, min(100.0, seg_score))
