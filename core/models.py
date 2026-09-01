"""
Pydantic Data Models and Schemas for SafePlace
Compliant with Appendix A and Core Architecture Specifications.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class POI(BaseModel):
    id: str
    name: str
    category: str  # 'police', 'hospital', 'pharmacy', 'public_building', 'transport_hub', 'fire_station', 'hotel', 'shelter'
    lat: float
    lon: float
    opening_hours: str = "24/7"
    accessibility: str = "wheelchair_accessible"  # 'full', 'partial', 'pedestrian_only'
    verification_status: str = "verified"  # 'verified', 'provisional', 'unverified'
    source: str = "Municipal_Safety_GIS"
    last_updated: str  # ISO-8601 string
    confidence: float = 85.0
    phone: Optional[str] = None
    address: Optional[str] = None
    capacity_level: Optional[str] = "normal"


class RoadSegment(BaseModel):
    id: str
    u_node: str
    v_node: str
    name: str
    road_type: str  # 'primary', 'secondary', 'residential', 'footway', 'alley'
    geometry: List[List[float]]  # List of [lat, lon] coordinates
    length_meters: float
    lighting: float = 0.8  # 0.0 (dark) to 1.0 (brightly lit)
    footpath: bool = True
    activity_proxy: float = 0.7  # 0.0 (isolated) to 1.0 (high footfall / busy)
    cctv_available: bool = False
    incident_density: float = 0.1  # 0.0 (none) to 1.0 (high incident history)
    speed_kmh: float = 4.5  # walking default
    last_updated: str
    confidence: float = 90.0


class IncidentAggregate(BaseModel):
    id: str
    area_grid: str
    lat: float
    lon: float
    radius_meters: float = 300.0
    time_bucket: str  # 'night', 'day', 'evening', 'all'
    category: str  # 'theft', 'harassment', 'poor_lighting_report', 'general_hazard'
    severity: float  # 1.0 (minor) to 5.0 (severe)
    count: int
    source: str = "Aggregated_Public_Safety_Records"
    confidence: float = 75.0
    last_updated: str


class ConfidenceScore(BaseModel):
    entity_id: str
    score: float  # 0.0 to 100.0
    tier: str  # 'HIGH', 'MODERATE', 'LOW', 'UNKNOWN'
    abstained: bool = False
    source_quality: float
    freshness: float
    completeness: float
    verification: float
    data_age_hours: float
    explanation: str


class SafetyScore(BaseModel):
    entity_id: str
    entity_type: str  # 'poi', 'route', 'area'
    safety_score: float  # 0.0 (dangerous) to 100.0 (very safe)
    risk_score: float  # 100.0 - safety_score
    breakdown: Dict[str, float]
    calculated_at: str
    model_version: str = "RiskModel_v1.0_Deterministic_ML"


class RouteStep(BaseModel):
    instruction: str
    distance_meters: float
    duration_seconds: float
    road_name: str
    lighting_level: str
    safety_indicator: str


class Route(BaseModel):
    id: str
    name: str
    mode: str = "walking"  # 'walking' or 'driving'
    destination_id: str
    destination_name: str
    destination_category: str
    path_nodes: List[str]
    path_coordinates: List[List[float]]  # [[lat, lon], ...]
    distance_meters: float
    duration_minutes: float
    safety_score: float
    risk_score: float
    confidence_score: float
    lighting_percentage: float
    emergency_proximity_score: float
    route_score: float  # Combined optimization metric
    is_safest: bool = False
    is_fastest: bool = False
    steps: List[RouteStep] = []
    why_recommended: List[str] = []


class SafeBubbleBand(BaseModel):
    minutes: int
    max_distance_meters: float
    destinations: List[Dict[str, Any]]


class SafeBubbleResult(BaseModel):
    user_lat: float
    user_lon: float
    calculated_at: str
    overall_zone_confidence: float
    is_in_safe_zone: bool
    status_message: str
    bands: List[SafeBubbleBand]
    recommended_destination: Optional[Dict[str, Any]] = None


class EmergencyPlan(BaseModel):
    status: str
    trigger_time: str
    user_location: Dict[str, float]
    safest_destination: POI
    destination_safety_score: float
    destination_confidence: float
    safest_route: Route
    fastest_route: Optional[Route] = None
    slm_guidance: str
    confidence_tier: str
    abstained: bool = False
    offline_status: bool = True
    recommended_action: str


class SLMQueryRequest(BaseModel):
    query: str
    user_lat: float
    user_lon: float
    data_age_hours_override: Optional[float] = None
    travel_mode: str = "walking"


class SLMResponse(BaseModel):
    query: str
    response_text: str
    abstained: bool
    confidence_tier: str
    confidence_score: float
    safety_score: Optional[float] = None
    tool_calls: List[Dict[str, Any]]
    evidence_grounding: Dict[str, Any]
    suggested_route: Optional[Route] = None
    suggested_poi: Optional[POI] = None
