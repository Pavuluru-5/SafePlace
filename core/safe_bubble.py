"""
SafePlace Dynamic Safe Bubble Monitor
Computes reachable trusted destinations across time bands (5, 10, 15 min isochrones)
and monitors user proximity to verified safety havens.
Compliant with Section 15.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
from core.models import POI, SafeBubbleResult, SafeBubbleBand
from core.database import OfflineDatabase, haversine_distance_meters
from core.risk_engine import SafetyRiskEngine
from core.confidence_engine import ConfidenceEngine
import config


class SafeBubbleMonitor:
    def __init__(self, db: OfflineDatabase, risk_engine: SafetyRiskEngine, confidence_engine: ConfidenceEngine):
        self.db = db
        self.risk_engine = risk_engine
        self.confidence_engine = confidence_engine

    def calculate_safe_bubble(
        self,
        user_lat: float,
        user_lon: float,
        travel_mode: str = "walking",
        age_hours_override: Optional[float] = None
    ) -> SafeBubbleResult:
        """
        Calculates dynamic reachable trusted places in 5, 10, and 15-minute time windows.
        """
        speed_kmh = config.WALKING_SPEED_KMH if travel_mode == "walking" else config.DRIVING_SPEED_KMH
        speed_meters_per_min = (speed_kmh * 1000.0) / 60.0

        all_pois = self.db.get_all_pois()
        evaluated_destinations = []

        for p in all_pois:
            dist_m = haversine_distance_meters(user_lat, user_lon, p.lat, p.lon)
            duration_min = dist_m / speed_meters_per_min

            safety = self.risk_engine.evaluate_poi_safety(p, user_lat, user_lon, age_hours_override=age_hours_override)
            conf = self.confidence_engine.evaluate_poi_confidence(p, age_hours_override=age_hours_override)

            evaluated_destinations.append({
                "poi": p,
                "distance_meters": round(dist_m, 1),
                "duration_minutes": round(duration_min, 1),
                "safety_score": safety.safety_score,
                "confidence_score": conf.score,
                "confidence_tier": conf.tier,
                "category": p.category,
                "name": p.name,
                "lat": p.lat,
                "lon": p.lon,
                "opening_hours": p.opening_hours,
                "accessibility": p.accessibility
            })

        # Sort by distance
        evaluated_destinations.sort(key=lambda x: x["distance_meters"])

        bands: List[SafeBubbleBand] = []
        for minutes in config.SAFE_BUBBLE_WINDOWS_MIN:
            max_dist = minutes * speed_meters_per_min
            band_dests = [
                d for d in evaluated_destinations 
                if d["distance_meters"] <= max_dist
            ]
            bands.append(SafeBubbleBand(
                minutes=minutes,
                max_distance_meters=round(max_dist, 1),
                destinations=band_dests
            ))

        # Overall zone evaluation
        in_10min = bands[1].destinations if len(bands) >= 2 else []
        high_conf_havens = [
            d for d in in_10min 
            if d["confidence_score"] >= config.CONFIDENCE_THRESHOLDS["MODERATE"] 
            and d["safety_score"] >= 70.0
        ]

        avg_zone_conf = sum(d["confidence_score"] for d in evaluated_destinations[:5]) / min(5, len(evaluated_destinations)) if evaluated_destinations else 80.0

        if len(high_conf_havens) >= 2:
            is_in_safe_zone = True
            status_msg = f"Safe Bubble Active: {len(high_conf_havens)} trusted havens reachable within 10 minutes."
        elif len(high_conf_havens) == 1:
            is_in_safe_zone = True
            status_msg = f"Safe Bubble Active: 1 trusted haven ({high_conf_havens[0]['name']}) reachable within 10 minutes."
        else:
            is_in_safe_zone = False
            status_msg = "Safe Bubble Advisory: Few or distant verified havens within walking radius."

        # Best recommended destination
        # Rank by combination of safety_score, confidence, and distance penalty
        def rank_score(d):
            dist_penalty = (d["distance_meters"] / 1000.0) * 15.0
            return (d["safety_score"] * 0.5) + (d["confidence_score"] * 0.3) - dist_penalty

        best_dest = max(evaluated_destinations, key=rank_score) if evaluated_destinations else None

        return SafeBubbleResult(
            user_lat=user_lat,
            user_lon=user_lon,
            calculated_at=datetime.now().isoformat(),
            overall_zone_confidence=round(avg_zone_conf, 1),
            is_in_safe_zone=is_in_safe_zone,
            status_message=status_msg,
            bands=bands,
            recommended_destination=best_dest
        )
