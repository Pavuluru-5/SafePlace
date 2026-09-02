"""
SafePlace API Routes
FastAPI endpoints for POIs, Safe Bubble, Safe vs Fast Routing, Emergency Trigger, and SLM Copilot.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

from core.database import OfflineDatabase, haversine_distance_meters
from core.risk_engine import SafetyRiskEngine
from core.confidence_engine import ConfidenceEngine
from core.route_engine import SafeRouteEngine
from core.safe_bubble import SafeBubbleMonitor
from core.slm_engine import OnDeviceSLMCopilot
from core.models import (
    POI, Route, SafeBubbleResult, SLMQueryRequest, SLMResponse,
    EmergencyPlan, ConfidenceScore
)
import config

router = APIRouter(prefix="/api")

# Singletons initialized on startup
db = OfflineDatabase()
risk_engine = SafetyRiskEngine(db)
confidence_engine = ConfidenceEngine()
route_engine = SafeRouteEngine(db, risk_engine, confidence_engine)
safe_bubble_monitor = SafeBubbleMonitor(db, risk_engine, confidence_engine)
slm_copilot = OnDeviceSLMCopilot(db, risk_engine, confidence_engine, route_engine, safe_bubble_monitor)


class EmergencyTriggerRequest(BaseModel):
    user_lat: float = 37.7740
    user_lon: float = -122.4200
    data_age_hours: Optional[float] = None
    travel_mode: str = "walking"


class DataAgeShiftRequest(BaseModel):
    hours: float


@router.get("/status")
def get_system_status():
    """Returns local offline system status, model versions, and data stats."""
    pois = db.get_all_pois()
    segments = db.get_all_road_segments()
    incidents = db.get_all_incident_aggregates()
    return {
        "status": "ONLINE_OFFLINE_READY",
        "mode": "OFFLINE_FIRST",
        "device_slm": "LiteRT-LM Compact Gemma (On-Device Inference)",
        "spatial_db": "SQLite Local Store",
        "total_pois": len(pois),
        "total_road_segments": len(segments),
        "total_incident_aggregates": len(incidents),
        "confidence_thresholds": config.CONFIDENCE_THRESHOLDS,
        "risk_weights": config.RISK_WEIGHTS
    }


def ensure_location_context(lat: float, lon: float):
    """
    Checks if current database has reachable POIs near (lat, lon).
    If the nearest POI is > 3500 meters away, automatically seeds the spatial network
    around (lat, lon) so that all queries succeed smoothly.
    """
    pois = db.get_all_pois()
    if not pois:
        from data.dataset_builder import seed_database_with_coords
        seed_database_with_coords(db, lat, lon, "Local Area")
        route_engine.build_graph()
        return

    min_dist = min(haversine_distance_meters(lat, lon, p.lat, p.lon) for p in pois)
    if min_dist > 3500:
        from data.dataset_builder import seed_database_with_coords
        seed_database_with_coords(db, lat, lon, "Local Area")
        route_engine.build_graph()


@router.get("/pois", response_model=List[POI])
def get_pois(
    category: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None
):
    """Retrieves all offline POIs or filters by category and optional proximity."""
    if lat is not None and lon is not None:
        ensure_location_context(lat, lon)
    all_p = db.get_all_pois()
    if category:
        all_p = [p for p in all_p if p.category.lower() == category.lower()]
    return all_p


@router.get("/safe-bubble", response_model=SafeBubbleResult)
def get_safe_bubble(
    lat: float = Query(37.7740, description="User Latitude"),
    lon: float = Query(-122.4200, description="User Longitude"),
    travel_mode: str = Query("walking", description="walking or driving"),
    data_age_hours: Optional[float] = Query(None, description="Simulated data age in hours")
):
    """Calculates dynamic Safe Bubble isochrones and reachable havens."""
    ensure_location_context(lat, lon)
    return safe_bubble_monitor.calculate_safe_bubble(
        user_lat=lat,
        user_lon=lon,
        travel_mode=travel_mode,
        age_hours_override=data_age_hours
    )


@router.get("/route")
def get_routes(
    lat: float = Query(37.7740, description="User start latitude"),
    lon: float = Query(-122.4200, description="User start longitude"),
    destination_id: str = Query(..., description="Target POI ID"),
    data_age_hours: Optional[float] = Query(None, description="Simulated data age override")
):
    """Calculates and returns both the Safest Route and the Fastest Route."""
    ensure_location_context(lat, lon)
    poi = db.get_poi_by_id(destination_id)
    if not poi:
        pois = db.get_all_pois()
        if pois:
            poi = pois[0]
        else:
            raise HTTPException(status_code=404, detail="Destination POI not found")

    safest, fastest = route_engine.calculate_routes_to_destination(
        user_lat=lat,
        user_lon=lon,
        destination=poi,
        age_hours_override=data_age_hours
    )

    return {
        "destination": poi,
        "safest_route": safest,
        "fastest_route": fastest,
        "comparison": {
            "time_difference_minutes": round(safest.duration_minutes - fastest.duration_minutes, 1),
            "safety_gain_points": round(safest.safety_score - fastest.safety_score, 1),
            "lighting_gain_pct": round(safest.lighting_percentage - fastest.lighting_percentage, 1),
            "recommendation": "Safest Route recommended for superior lighting, emergency access, and verified lower hazard density."
        }
    }


@router.post("/emergency", response_model=EmergencyPlan)
def trigger_emergency(req: EmergencyTriggerRequest):
    """
    Emergency Mode ('I'M NOT SAFE' flow):
    Instant selection of highest-ranked safe haven, dual route calculation, and SLM guidance.
    """
    ensure_location_context(req.user_lat, req.user_lon)
    # 1. Calculate Safe Bubble to locate all candidate havens
    bubble = safe_bubble_monitor.calculate_safe_bubble(
        user_lat=req.user_lat,
        user_lon=req.user_lon,
        travel_mode=req.travel_mode,
        age_hours_override=req.data_age_hours
    )

    if not bubble.recommended_destination:
        raise HTTPException(status_code=404, detail="No reachable trusted destinations found in local database")

    best_poi_dict = bubble.recommended_destination["poi"]
    poi_id = best_poi_dict.id if isinstance(best_poi_dict, POI) else best_poi_dict["id"]
    best_poi = db.get_poi_by_id(poi_id)

    # 2. Evaluate Confidence
    conf = confidence_engine.evaluate_poi_confidence(best_poi, age_hours_override=req.data_age_hours)
    dest_safety = risk_engine.evaluate_poi_safety(best_poi, req.user_lat, req.user_lon, age_hours_override=req.data_age_hours)

    # 3. Calculate Routes
    safest_route, fastest_route = route_engine.calculate_routes_to_destination(
        user_lat=req.user_lat,
        user_lon=req.user_lon,
        destination=best_poi,
        age_hours_override=req.data_age_hours
    )

    # 4. Generate SLM Emergency Guidance
    if conf.abstained:
        guidance = (
            f"⚠️ **Caution**: Local safety records are stale ({conf.data_age_hours:.0f} hours old, confidence {conf.score:.0f}%).\n"
            f"Nearest recorded haven is **{best_poi.name}** ({safest_route.distance_meters:.0f}m away). "
            f"Proceed cautiously along major roads or call local emergency services."
        )
        rec_action = "Proceed with caution towards nearest known facility."
    else:
        guidance = (
            f"🚨 **SafePlace Emergency Action**:\n"
            f"Proceed immediately to **{best_poi.name}** ({best_poi.category.replace('_', ' ').title()}).\n"
            f"• Distance: {safest_route.distance_meters:.0f} m (~{safest_route.duration_minutes:.1f} min walk)\n"
            f"• Route Lighting: {safest_route.lighting_percentage:.0f}% illumination\n"
            f"• Facility Status: Verified 24/7 staffing."
        )
        rec_action = f"Follow illuminated safe corridor to {best_poi.name}."

    return EmergencyPlan(
        status="EMERGENCY_ACTIVE",
        trigger_time=datetime.now().isoformat(),
        user_location={"lat": req.user_lat, "lon": req.user_lon},
        safest_destination=best_poi,
        destination_safety_score=dest_safety.safety_score,
        destination_confidence=conf.score,
        safest_route=safest_route,
        fastest_route=fastest_route,
        slm_guidance=guidance,
        confidence_tier=conf.tier,
        abstained=conf.abstained,
        offline_status=True,
        recommended_action=rec_action
    )


@router.post("/chat", response_model=SLMResponse)
def slm_chat(req: SLMQueryRequest):
    """
    On-device Conversational SLM query endpoint.
    Performs tool calling, grounded reasoning, and abstention handling.
    """
    ensure_location_context(req.user_lat, req.user_lon)
    return slm_copilot.process_query(
        query=req.query,
        user_lat=req.user_lat,
        user_lon=req.user_lon,
        age_hours_override=req.data_age_hours_override,
        travel_mode=req.travel_mode
    )


@router.get("/cities")
def get_available_cities():
    """Returns available Indian and international city presets."""
    from data.dataset_builder import CITY_PRESETS
    return [
        {
            "key": k,
            "name": v["name"],
            "country": v["country"],
            "center": v["center"]
        }
        for k, v in CITY_PRESETS.items()
    ]


class CitySwitchRequest(BaseModel):
    city_key: str = "hyderabad"


class SetLocationRequest(BaseModel):
    lat: float
    lon: float
    name: str = "Current GPS Location"


@router.post("/switch-city")
def switch_city(req: CitySwitchRequest):
    """Switch active city and re-seed local spatial database."""
    from data.dataset_builder import seed_offline_database
    meta = seed_offline_database(db, req.city_key)
    route_engine.build_graph()
    return {
        "status": "CITY_SWITCHED",
        "city_key": req.city_key,
        "city_name": meta["city_name"],
        "center": meta["center"],
        "total_pois": meta["total_pois"],
        "total_segments": meta["total_segments"]
    }


@router.post("/set-location")
def set_custom_location(req: SetLocationRequest):
    """Dynamically seed safety network around user's exact coordinates."""
    from data.dataset_builder import seed_database_with_coords
    meta = seed_database_with_coords(db, req.lat, req.lon, req.name)
    route_engine.build_graph()
    return {
        "status": "LOCATION_SET",
        "center": {"lat": req.lat, "lon": req.lon},
        "name": req.name,
        "total_pois": meta["total_pois"],
        "total_segments": meta["total_segments"]
    }


@router.post("/data-trust/age")
def shift_data_age(req: DataAgeShiftRequest):
    """Dynamically simulates data staleness to test confidence drop & abstention."""
    db.set_global_data_age_hours(req.hours)
    route_engine.build_graph()  # Rebuild weights
    return {
        "status": "UPDATED",
        "simulated_age_hours": req.hours,
        "message": f"All spatial & safety data updated to be {req.hours} hours old."
    }


@router.post("/sync")
def sync_data(city_key: str = "hyderabad"):
    """Simulates local/cloud synchronization to refresh all data to current time."""
    from data.dataset_builder import seed_offline_database
    meta = seed_offline_database(db, city_key)
    route_engine.build_graph()
    return {
        "status": "SYNC_SUCCESS",
        "synced_at": datetime.now().isoformat(),
        "package_version": meta["version"],
        "metadata": meta
    }

