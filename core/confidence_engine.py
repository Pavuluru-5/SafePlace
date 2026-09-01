"""
SafePlace Confidence & Data Trust Engine
Calculates evidence reliability, freshness decay, and triggers the "I Don't Know" abstention mechanism.
Compliant with Section 11, Section 12, and Appendix B.
"""

import math
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from core.models import ConfidenceScore, POI, RoadSegment
import config


class ConfidenceEngine:
    def __init__(self, thresholds: Optional[Dict[str, float]] = None, weights: Optional[Dict[str, float]] = None):
        self.thresholds = thresholds or config.CONFIDENCE_THRESHOLDS
        self.weights = weights or config.CONFIDENCE_WEIGHTS

    def calculate_data_age_hours(self, last_updated_str: str) -> float:
        """Parse timestamp and calculate elapsed hours."""
        try:
            # Handle ISO formats
            if last_updated_str.endswith('Z'):
                dt = datetime.fromisoformat(last_updated_str[:-1])
            else:
                dt = datetime.fromisoformat(last_updated_str)
            now = datetime.now()
            diff = now - dt
            return max(0.0, diff.total_seconds() / 3600.0)
        except Exception:
            # Fallback for unparseable timestamps
            return 720.0  # assume 30 days old

    def calculate_freshness_score(self, age_hours: float) -> float:
        """
        Calculates freshness score (0-100) using a dynamic half-life decay:
        - 0 to 6 hours: 100%
        - 24 hours (1 day): ~88%
        - 72 hours (3 days): ~62%
        - 168 hours (7 days): ~31%
        - 336 hours (14 days): ~9%
        - > 700 hours (1 month+): < 1%
        """
        if age_hours <= 6.0:
            return 100.0
        half_life_hours = 96.0  # 4 days half-life for safety-critical telemetry
        freshness = 100.0 * math.exp(-0.693 * ((age_hours - 6.0) / half_life_hours))
        return max(0.0, min(100.0, freshness))

    def evaluate_poi_confidence(self, poi: POI, age_hours_override: Optional[float] = None) -> ConfidenceScore:
        """Evaluates confidence for a POI."""
        age_hours = age_hours_override if age_hours_override is not None else self.calculate_data_age_hours(poi.last_updated)
        freshness = self.calculate_freshness_score(age_hours)

        # Source Quality (0-100)
        source_map = {
            "Municipal_Safety_GIS": 95.0,
            "National_Emergency_Registry": 98.0,
            "Hospital_Authority_Direct": 95.0,
            "Police_Department_Feed": 98.0,
            "OpenStreetMap_Verified": 80.0,
            "Crowdsourced_Community": 60.0,
            "Estimated_Proxy": 45.0
        }
        source_quality = source_map.get(poi.source, 70.0)

        # Verification Status (0-100)
        verification_map = {
            "verified": 95.0,
            "provisional": 65.0,
            "unverified": 35.0
        }
        verification = verification_map.get(poi.verification_status.lower(), 50.0)

        # Completeness (0-100)
        completeness_checks = [
            bool(poi.name),
            bool(poi.lat and poi.lon),
            bool(poi.category),
            bool(poi.opening_hours),
            bool(poi.accessibility),
            bool(poi.phone or poi.address)
        ]
        completeness = (sum(completeness_checks) / len(completeness_checks)) * 100.0

        # Weighted Confidence Score
        raw_score = (
            source_quality * self.weights["source_quality"] +
            freshness * self.weights["freshness"] +
            completeness * self.weights["completeness"] +
            verification * self.weights["verification"]
        )
        
        # Temporal Safety Gating: If evidence is stale, confidence cannot exceed freshness multiplier
        if freshness < 40.0:
            score = min(raw_score, max(freshness * 1.1, 5.0))
        else:
            score = raw_score
            
        score = max(0.0, min(100.0, score))

        # Determine Tier and Abstention
        if score >= self.thresholds["HIGH"]:
            tier = "HIGH"
            abstained = False
            explanation = f"High confidence ({score:.1f}%): Verified source, updated {age_hours:.1f}h ago."
        elif score >= self.thresholds["MODERATE"]:
            tier = "MODERATE"
            abstained = False
            explanation = f"Moderate confidence ({score:.1f}%): Recommendation with standard caution. Data age: {age_hours:.1f}h."
        elif score >= self.thresholds["LOW"]:
            tier = "LOW"
            abstained = False
            explanation = f"Low confidence ({score:.1f}%): Limited supporting verification or older data ({age_hours:.1f}h)."
        else:
            tier = "UNKNOWN"
            abstained = True
            explanation = f"UNKNOWN / ABSTAIN ({score:.1f}%): Insufficient or stale evidence ({age_hours:.1f}h old). System explicitly abstains from making an ungrounded safety guarantee."

        return ConfidenceScore(
            entity_id=poi.id,
            score=round(score, 1),
            tier=tier,
            abstained=abstained,
            source_quality=round(source_quality, 1),
            freshness=round(freshness, 1),
            completeness=round(completeness, 1),
            verification=round(verification, 1),
            data_age_hours=round(age_hours, 1),
            explanation=explanation
        )

    def evaluate_route_confidence(self, road_segments: list[RoadSegment], age_hours_override: Optional[float] = None) -> ConfidenceScore:
        """Evaluates confidence for an entire route based on constituent segments."""
        if not road_segments:
            return ConfidenceScore(
                entity_id="empty_route",
                score=0.0,
                tier="UNKNOWN",
                abstained=True,
                source_quality=0.0,
                freshness=0.0,
                completeness=0.0,
                verification=0.0,
                data_age_hours=999.0,
                explanation="Route contains no segments."
            )

        segment_scores = []
        total_age = 0.0
        for seg in road_segments:
            age_hours = age_hours_override if age_hours_override is not None else self.calculate_data_age_hours(seg.last_updated)
            freshness = self.calculate_freshness_score(age_hours)
            source_quality = 85.0
            verification = 85.0 if seg.lighting > 0.5 else 70.0
            completeness = 90.0 if seg.geometry and len(seg.geometry) >= 2 else 50.0

            s = (
                source_quality * self.weights["source_quality"] +
                freshness * self.weights["freshness"] +
                completeness * self.weights["completeness"] +
                verification * self.weights["verification"]
            )
            segment_scores.append(s)
            total_age += age_hours

        avg_score = sum(segment_scores) / len(segment_scores)
        avg_age = total_age / len(road_segments)

        if avg_score >= self.thresholds["HIGH"]:
            tier = "HIGH"
            abstained = False
            explanation = f"High confidence route ({avg_score:.1f}%): Supported by verified infrastructure data."
        elif avg_score >= self.thresholds["MODERATE"]:
            tier = "MODERATE"
            abstained = False
            explanation = f"Moderate confidence route ({avg_score:.1f}%): Minor gaps or moderate age."
        elif avg_score >= self.thresholds["LOW"]:
            tier = "LOW"
            abstained = False
            explanation = f"Low confidence route ({avg_score:.1f}%): Limited road telemetry."
        else:
            tier = "UNKNOWN"
            abstained = True
            explanation = f"UNKNOWN / ABSTAIN ({avg_score:.1f}%): Stale or incomplete road infrastructure evidence."

        return ConfidenceScore(
            entity_id="route_aggregated",
            score=round(avg_score, 1),
            tier=tier,
            abstained=abstained,
            source_quality=85.0,
            freshness=round(self.calculate_freshness_score(avg_age), 1),
            completeness=90.0,
            verification=80.0,
            data_age_hours=round(avg_age, 1),
            explanation=explanation
        )
