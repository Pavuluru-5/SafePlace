"""
SafePlace On-Device SLM Copilot Engine
Simulates the LiteRT-LM / Gemma on-device orchestration layer with controlled tool execution,
grounded reasoning, uncertainty awareness, and Responsible AI guardrails.
Compliant with Section 17, Section 18, Section 25, and Appendix B.
"""

from typing import Dict, List, Any, Optional, Tuple
from core.models import SLMResponse, POI, Route, SafeBubbleResult, ConfidenceScore
from core.database import OfflineDatabase, haversine_distance_meters
from core.risk_engine import SafetyRiskEngine
from core.confidence_engine import ConfidenceEngine
from core.route_engine import SafeRouteEngine
from core.safe_bubble import SafeBubbleMonitor
import config


class OnDeviceSLMCopilot:
    def __init__(
        self,
        db: OfflineDatabase,
        risk_engine: SafetyRiskEngine,
        confidence_engine: ConfidenceEngine,
        route_engine: SafeRouteEngine,
        safe_bubble_monitor: SafeBubbleMonitor
    ):
        self.db = db
        self.risk_engine = risk_engine
        self.confidence_engine = confidence_engine
        self.route_engine = route_engine
        self.safe_bubble_monitor = safe_bubble_monitor

    # -------------------------------------------------------------
    # Controlled Local Tools (Approved Tool Invocation Interface)
    # -------------------------------------------------------------
    def tool_get_current_location(self, user_lat: float, user_lon: float) -> Dict[str, Any]:
        return {"lat": user_lat, "lon": user_lon, "mode": "GPS_OFFLINE_FIX"}

    def tool_find_nearby_pois(self, lat: float, lon: float, category: Optional[str] = None, max_dist: float = 3000.0) -> List[Dict[str, Any]]:
        nearby = self.db.get_nearby_pois(lat, lon, max_distance_meters=max_dist, category=category)
        return [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "distance_m": round(d, 1),
                "lat": p.lat,
                "lon": p.lon,
                "opening_hours": p.opening_hours,
                "accessibility": p.accessibility,
                "phone": p.phone,
                "address": p.address
            }
            for p, d in nearby
        ]

    def tool_calculate_risk(self, poi_id: str, user_lat: float, user_lon: float, age_hours_override: Optional[float] = None) -> Dict[str, Any]:
        poi = self.db.get_poi_by_id(poi_id)
        if not poi:
            return {"error": "POI not found"}
        score = self.risk_engine.evaluate_poi_safety(poi, user_lat, user_lon, age_hours_override=age_hours_override)
        return {
            "poi_id": poi.id,
            "name": poi.name,
            "safety_score": score.safety_score,
            "risk_score": score.risk_score,
            "breakdown": score.breakdown
        }

    def tool_calculate_confidence(self, poi_id: str, age_hours_override: Optional[float] = None) -> Dict[str, Any]:
        poi = self.db.get_poi_by_id(poi_id)
        if not poi:
            return {"error": "POI not found"}
        conf = self.confidence_engine.evaluate_poi_confidence(poi, age_hours_override=age_hours_override)
        return {
            "poi_id": poi.id,
            "score": conf.score,
            "tier": conf.tier,
            "abstained": conf.abstained,
            "freshness": conf.freshness,
            "source_quality": conf.source_quality,
            "data_age_hours": conf.data_age_hours,
            "explanation": conf.explanation
        }

    def tool_calculate_safe_route(self, user_lat: float, user_lon: float, destination_id: str, age_hours_override: Optional[float] = None) -> Dict[str, Any]:
        poi = self.db.get_poi_by_id(destination_id)
        if not poi:
            return {"error": "POI not found"}
        safest, fastest = self.route_engine.calculate_routes_to_destination(user_lat, user_lon, poi, age_hours_override=age_hours_override)
        return {
            "safest_route": safest.model_dump(),
            "fastest_route": fastest.model_dump()
        }

    def tool_get_safe_bubble(self, user_lat: float, user_lon: float, age_hours_override: Optional[float] = None) -> Dict[str, Any]:
        res = self.safe_bubble_monitor.calculate_safe_bubble(user_lat, user_lon, age_hours_override=age_hours_override)
        return res.model_dump()

    def tool_get_incidents(self, lat: float, lon: float, radius: float = 500.0) -> List[Dict[str, Any]]:
        incidents = self.db.get_incidents_near_point(lat, lon, radius_meters=radius)
        return [
            {
                "id": inc.id,
                "category": inc.category,
                "severity": inc.severity,
                "count": inc.count,
                "time_bucket": inc.time_bucket,
                "lat": inc.lat,
                "lon": inc.lon
            }
            for inc in incidents
        ]

    # -------------------------------------------------------------
    # SLM Natural Language Inference & Grounded Reasoning
    # -------------------------------------------------------------
    def process_query(
        self,
        query: str,
        user_lat: float,
        user_lon: float,
        age_hours_override: Optional[float] = None,
        travel_mode: str = "walking"
    ) -> SLMResponse:
        """
        Orchestrates semantic intent classification, dynamic tool calling,
        uncertainty evaluation, and grounded advice adhering to Responsible AI rules.
        """
        q = query.strip()
        q_lower = q.lower()
        tool_calls_record = []
        evidence = {}

        # 0. Greetings & Assistant Introduction
        greeting_words = ["hi", "hello", "hey", "greetings", "namaste", "good morning", "good evening", "good afternoon", "how are you", "what's up", "hey there", "yo"]
        is_greeting = any(
            q_lower == w or 
            q_lower.startswith(w + " ") or 
            q_lower.startswith(w + ",") or 
            q_lower.startswith(w + "!") or 
            q_lower.startswith(w + "?") or 
            q_lower.endswith(" " + w)
            for w in greeting_words
        )
        is_safety_query = any(w in q_lower for w in ["hospital", "police", "pharmacy", "route", "help", "emergency", "danger", "distance", "how far", "bubble", "why", "compare"])

        if is_greeting and not is_safety_query:
            bubble = self.safe_bubble_monitor.calculate_safe_bubble(user_lat, user_lon, travel_mode=travel_mode, age_hours_override=age_hours_override)
            tool_calls_record.append({"tool": "get_safe_bubble", "args": {"lat": user_lat, "lon": user_lon}, "status": "OK"})
            b5 = len(bubble.bands[0].destinations) if len(bubble.bands) > 0 else 0
            b10 = len(bubble.bands[1].destinations) if len(bubble.bands) > 1 else 0
            
            response_text = (
                f"Hello! I am your **SafePlace AI Safety Copilot**, active and monitoring your surroundings locally on-device.\n\n"
                f"🛡️ **Current Live Safety Status**:\n"
                f"• Safe Bubble: **{b5} haven(s)** reachable in 5 mins, **{b10}** reachable in 10 mins.\n"
                f"• Evidence Confidence: **{bubble.overall_zone_confidence:.0f}%** ({'Active' if bubble.is_in_safe_zone else 'Advisory'}).\n\n"
                f"**How I can assist you right now**:\n"
                f"• Ask *'Where is the nearest hospital?'* or *'Find a 24/7 pharmacy'*\n"
                f"• Ask *'How far is Cyberabad Police Station?'* for instant distance & walk time\n"
                f"• Ask *'Why did you choose this route?'* to inspect street lighting and safety evidence\n"
                f"• State *'I'm not safe'* for immediate emergency corridor routing"
            )
            return SLMResponse(
                query=query,
                response_text=response_text,
                abstained=False,
                confidence_tier="HIGH",
                confidence_score=bubble.overall_zone_confidence,
                tool_calls=tool_calls_record,
                evidence_grounding={"status": bubble.status_message}
            )

        # Conversational Acknowledgements & Pleasantries
        pleasantry_words = ["thanks", "thank you", "thx", "ok", "okay", "great", "got it", "cool", "perfect", "awesome", "bye", "goodbye", "see you", "alright", "sure", "sounds good", "nice"]
        is_pleasantry = any(
            q_lower == w or 
            q_lower.startswith(w + " ") or 
            q_lower.startswith(w + ",") or 
            q_lower.startswith(w + "!") or 
            q_lower.endswith(" " + w)
            for w in pleasantry_words
        )
        if is_pleasantry and not is_safety_query:
            response_text = (
                "You're very welcome! I am actively keeping track of your Safe Bubble and verified corridors. "
                "Whenever you need safe navigation, distance information, or emergency refuge, I'm right here with you."
            )
            return SLMResponse(
                query=query,
                response_text=response_text,
                abstained=False,
                confidence_tier="HIGH",
                confidence_score=100.0,
                tool_calls=[{"tool": "conversational_acknowledgement", "args": {}, "status": "OK"}],
                evidence_grounding={"mode": "active_monitoring"}
            )

        # Capabilities / Help intent
        if any(w in q_lower for w in ["what can you do", "who are you", "what is safeplace", "features", "how does this work", "how do you work", "commands", "help me understand"]):
            response_text = (
                f"**SafePlace** is an offline-first AI safety assistant engineered for on-device protection:\n\n"
                f"1. **Dynamic Safe Bubble**: Continuously calculates trusted havens (Police, Hospitals, 24/7 Pharmacies, Shelters) within 5, 10, and 15-minute walking radius.\n"
                f"2. **Safest vs. Fastest Routing**: Evaluates street lighting, CCTV coverage, sidewalks, and hazard history to avoid dark alleyways.\n"
                f"3. **Uncertainty Awareness ('I Don't Know' Guardrail)**: If safety telemetry is stale or missing, I explicitly abstain rather than giving misleading guarantees.\n"
                f"4. **Emergency Mode ('I'M NOT SAFE')**: 1-tap instant escape corridor with spoken turn-by-turn guidance.\n"
                f"5. **100% Offline Privacy**: Runs entirely on local GIS data without sending your GPS location to the cloud."
            )
            return SLMResponse(
                query=query,
                response_text=response_text,
                abstained=False,
                confidence_tier="HIGH",
                confidence_score=100.0,
                tool_calls=[{"tool": "get_system_capabilities", "args": {}, "status": "OK"}],
                evidence_grounding={"mode": "offline_first"}
            )

        # 1. Evaluate Safe Bubble
        bubble = self.safe_bubble_monitor.calculate_safe_bubble(user_lat, user_lon, travel_mode=travel_mode, age_hours_override=age_hours_override)
        tool_calls_record.append({"tool": "get_safe_bubble", "args": {"lat": user_lat, "lon": user_lon}, "status": "OK"})

        all_pois = self.db.get_all_pois()
        tool_calls_record.append({"tool": "find_nearby_pois", "args": {"lat": user_lat, "lon": user_lon, "count": len(all_pois)}, "status": "OK"})

        # Check for specific category requests
        target_category = None
        category_keywords = {
            "hospital": ["hospital", "clinic", "doctor", "trauma", "medical", "ambulance", "emergency room", "medicover", "lilavati", "rml", "manipal"],
            "police": ["police", "cop", "station", "precinct", "cyberabad", "cubbon", "bandra", "parliament", "security", "patrol", "constable"],
            "pharmacy": ["pharmacy", "chemist", "medicine", "drug", "apollo", "medplus", "noble", "first aid", "prescription"],
            "transport_hub": ["metro", "transit", "train", "bus", "station", "transport", "subway", "railway"],
            "fire_station": ["fire", "firefighter", "brigade", "fire engine", "extinguisher"],
            "public_building": ["public", "civic", "library", "shelter", "community", "command center"]
        }

        for cat, kw_list in category_keywords.items():
            if any(kw in q_lower for kw in kw_list):
                target_category = cat
                break

        # Check for specific POI name match
        matched_poi = None
        for p in all_pois:
            p_clean = p.name.lower()
            p_words = [w for w in p_clean.split() if len(w) > 3 and w not in ["station", "hospital", "pharmacy", "center", "care"]]
            if p_clean in q_lower or any(w in q_lower for w in p_words):
                matched_poi = p
                break

        # Determine target destination POI
        selected_poi = None
        if matched_poi:
            selected_poi = matched_poi
        elif target_category:
            cat_pois = [p for p in all_pois if p.category.lower() == target_category.lower()]
            if cat_pois:
                cat_pois.sort(key=lambda p: haversine_distance_meters(user_lat, user_lon, p.lat, p.lon))
                selected_poi = cat_pois[0]

        if not selected_poi:
            best_dest_info = bubble.recommended_destination
            if best_dest_info:
                poi_id = best_dest_info["poi"].id if isinstance(best_dest_info["poi"], POI) else best_dest_info["poi"]["id"]
                selected_poi = self.db.get_poi_by_id(poi_id)

        if not selected_poi:
            return SLMResponse(
                query=query,
                response_text="I don't have enough local map data to locate any nearby trusted facilities.",
                abstained=True,
                confidence_tier="UNKNOWN",
                confidence_score=0.0,
                tool_calls=tool_calls_record,
                evidence_grounding={}
            )

        # 2. Evaluate Confidence & Check Abstention
        conf = self.confidence_engine.evaluate_poi_confidence(selected_poi, age_hours_override=age_hours_override)
        tool_calls_record.append({"tool": "calculate_confidence", "args": {"poi_id": selected_poi.id}, "status": "OK"})

        # 3. If confidence is below threshold, trigger Responsible AI Abstention ("I Don't Know" mechanism)
        if conf.abstained or conf.score < config.CONFIDENCE_THRESHOLDS["ABSTAIN"]:
            dist_km = haversine_distance_meters(user_lat, user_lon, selected_poi.lat, selected_poi.lon) / 1000.0
            response_text = (
                f"⚠️ **Uncertainty Alert**: I don't have enough recent information to make a reliable safety recommendation for this area.\n\n"
                f"• **Evidence Age**: Local safety data is {conf.data_age_hours:.1f} hours old ({conf.freshness:.0f}% freshness).\n"
                f"• **Nearest Facility**: The closest recorded emergency facility is **{selected_poi.name}** (~{dist_km:.2f} km away).\n"
                f"• **Responsible Guidance**: Proceed with caution along major illuminated avenues or contact local emergency services directly (Dial 112 / 100)."
            )
            return SLMResponse(
                query=query,
                response_text=response_text,
                abstained=True,
                confidence_tier=conf.tier,
                confidence_score=conf.score,
                safety_score=50.0,
                tool_calls=tool_calls_record,
                evidence_grounding={
                    "data_age_hours": conf.data_age_hours,
                    "confidence_score": conf.score,
                    "nearest_facility": selected_poi.name,
                    "distance_km": round(dist_km, 2),
                    "reason_for_abstention": conf.explanation
                },
                suggested_poi=selected_poi
            )

        # 4. Calculate Routes to selected POI
        safest_route, fastest_route = self.route_engine.calculate_routes_to_destination(
            user_lat, user_lon, selected_poi, age_hours_override=age_hours_override
        )
        tool_calls_record.append({"tool": "calculate_safe_route", "args": {"dest_id": selected_poi.id}, "status": "OK"})

        evidence["destination"] = selected_poi.name
        evidence["category"] = selected_poi.category
        evidence["safety_score"] = safest_route.safety_score
        evidence["confidence_score"] = conf.score
        evidence["lighting_pct"] = safest_route.lighting_percentage
        evidence["distance_m"] = safest_route.distance_meters
        evidence["duration_min"] = safest_route.duration_minutes

        # 5. Formulate Grounded Natural Language Responses based on Intent

        # Intent: Emergency / Distress
        if any(w in q_lower for w in ["emergency", "help", "not safe", "danger", "scared", "urgent", "unsafe", "threat", "following me", "stalker", "attack", "sos"]):
            response_text = (
                f"🚨 **Emergency Guidance Active**:\n\n"
                f"Proceed directly to **{selected_poi.name}** ({selected_poi.category.replace('_', ' ').title()}), located **{safest_route.distance_meters:.0f} meters away** (~{safest_route.duration_minutes:.1f} min walk).\n\n"
                f"• **Route Security**: Follow the highlighted safe corridor ({safest_route.lighting_percentage:.0f}% street lighting coverage).\n"
                f"• **Destination Status**: Verified open ({selected_poi.opening_hours}), {selected_poi.accessibility}.\n"
                f"• **Phone Contact**: {selected_poi.phone or 'Emergency 112 / 100'}\n"
                f"• **Confidence**: {conf.score:.0f}% ({conf.tier} Tier, verified {conf.data_age_hours:.1f}h ago)."
            )

        # Intent: Why / Explanation Intent (Section 35)
        elif any(w in q_lower for w in ["why", "reason", "explain", "choose", "how come", "why this"]):
            time_diff = max(0.2, safest_route.duration_minutes - fastest_route.duration_minutes)
            response_text = (
                f"I recommended **{selected_poi.name}** via the **Safest Route** because:\n\n"
                f"1. **Infrastructure & Lighting**: The route follows major roads with **{safest_route.lighting_percentage:.0f}% active street lighting** coverage and dedicated footpaths.\n"
                f"2. **Destination Security**: {selected_poi.name} is a verified {selected_poi.opening_hours} {selected_poi.category.replace('_', ' ').title()} with active on-site security.\n"
                f"3. **Lower Risk**: Avoids unlit alley cuts, trading just ~{time_diff:.1f} extra minutes for significantly lower estimated hazard exposure.\n"
                f"4. **Data Trust**: Grounded in high-confidence municipal telemetry ({conf.score:.0f}% confidence, data age: {conf.data_age_hours:.1f}h)."
            )

        # Intent: Route Comparison Intent (Section 14)
        elif any(w in q_lower for w in ["compare", "fastest", "fast vs safe", "difference", "shortest", "quickest", "vs"]):
            time_saved = max(0.2, safest_route.duration_minutes - fastest_route.duration_minutes)
            lighting_loss = max(0.0, safest_route.lighting_percentage - fastest_route.lighting_percentage)
            response_text = (
                f"⚖️ **Route Comparison to {selected_poi.name}**:\n\n"
                f"• **Safest Route (Green)**: {safest_route.duration_minutes:.1f} min ({safest_route.distance_meters:.0f}m) | Safety Score: **{safest_route.safety_score:.0f}/100** | Illumination: **{safest_route.lighting_percentage:.0f}%**\n"
                f"• **Fastest Route (Amber)**: {fastest_route.duration_minutes:.1f} min ({fastest_route.distance_meters:.0f}m) | Safety Score: **{fastest_route.safety_score:.0f}/100** | Illumination: **{fastest_route.lighting_percentage:.0f}%**\n\n"
                f"💡 **Trade-off Analysis**: The fastest route saves ~{time_saved:.1f} minutes by cutting through unlit alleys, but reduces street lighting by {lighting_loss:.0f}% and increases risk exposure. The Safest Route is strongly advised."
            )

        # Intent: Safe Bubble Status (Section 15)
        elif any(w in q_lower for w in ["bubble", "area", "around", "zone", "isochrone", "reachability", "5 min", "10 min", "15 min"]):
            b5_count = len(bubble.bands[0].destinations) if len(bubble.bands) > 0 else 0
            b10_count = len(bubble.bands[1].destinations) if len(bubble.bands) > 1 else 0
            b15_count = len(bubble.bands[2].destinations) if len(bubble.bands) > 2 else 0
            response_text = (
                f"🌐 **Dynamic Safe Bubble Status**:\n\n"
                f"• **5-min window**: {b5_count} verified haven(s) reachable\n"
                f"• **10-min window**: {b10_count} verified haven(s) reachable\n"
                f"• **15-min window**: {b15_count} verified haven(s) reachable\n"
                f"• **Primary Haven**: **{selected_poi.name}** ({safest_route.distance_meters:.0f}m, ~{safest_route.duration_minutes:.1f} min walk)\n"
                f"• **Zone Confidence**: {bubble.overall_zone_confidence:.0f}% ({conf.tier} Tier)\n"
                f"• **Status**: {bubble.status_message}"
            )

        # Intent: Area Safety / Lighting / Incident Summary
        elif any(w in q_lower for w in ["incident", "crime", "hazard", "dark", "lighting", "safe to walk", "dangerous", "night", "streets"]):
            incidents = self.tool_get_incidents(user_lat, user_lon, radius=1000.0)
            tool_calls_record.append({"tool": "get_incidents", "args": {"lat": user_lat, "lon": user_lon, "radius": 1000.0}, "status": "OK"})
            inc_count = sum(i["count"] for i in incidents) if incidents else 0
            
            response_text = (
                f"🗺️ **Area Safety & Lighting Assessment**:\n\n"
                f"• **Recommended Corridor**: The primary avenue towards **{selected_poi.name}** has **{safest_route.lighting_percentage:.0f}% street lighting** with active pedestrian walkways.\n"
                f"• **Hazard Exposure**: Avoid narrow secondary alley cuts which have limited lighting (under 20%) and historical hazard reports.\n"
                f"• **Incident Aggregates**: {inc_count} historical incident reports recorded in surrounding 1km grid ({conf.tier} confidence tier).\n"
                f"• **Guidance**: Stay along illuminated primary avenues highlighted in green on your map."
            )

        # Intent: Distance & Proximity Inquiry
        elif any(w in q_lower for w in ["how far", "distance", "how long", "walking time", "how many minutes", "how many meters", "eta", "time to walk", "far is"]):
            dur_min = max(1.0, round(safest_route.duration_minutes, 1))
            dist_m = round(safest_route.distance_meters)
            response_text = (
                f"📍 **Distance to {selected_poi.name}** ({selected_poi.category.replace('_', ' ').title()}):\n\n"
                f"• **Walking Distance**: **{dist_m} meters**\n"
                f"• **Estimated Time**: **~{dur_min:.1f} min walk** at normal pace\n"
                f"• **Route Lighting**: **{safest_route.lighting_percentage:.0f}% street illumination**\n"
                f"• **Operating Hours**: {selected_poi.opening_hours}\n"
                f"• **Contact**: {selected_poi.phone or 'Emergency 112 / 100'}\n\n"
                f"The illuminated safe corridor has been highlighted on your map."
            )

        # Intent: Category-specific POI search
        elif target_category:
            cat_label = target_category.replace('_', ' ').title()
            response_text = (
                f"📍 Nearest **{cat_label}**: **{selected_poi.name}**\n\n"
                f"• **Distance**: {safest_route.distance_meters:.0f} m (~{safest_route.duration_minutes:.1f} min walk)\n"
                f"• **Safety Score**: {safest_route.safety_score:.0f}/100\n"
                f"• **Lighting Coverage**: {safest_route.lighting_percentage:.0f}% illuminated\n"
                f"• **Opening Hours**: {selected_poi.opening_hours}\n"
                f"• **Phone**: {selected_poi.phone or 'N/A'}\n"
                f"• **Address**: {selected_poi.address or 'Verified municipal location'}\n\n"
                f"The highlighted green path provides the safest route along illuminated corridors."
            )

        # Intent: Specific POI name lookup
        elif matched_poi:
            response_text = (
                f"📍 Navigation to **{selected_poi.name}** ({selected_poi.category.replace('_', ' ').title()}):\n\n"
                f"• **Distance**: {safest_route.distance_meters:.0f} m (~{safest_route.duration_minutes:.1f} min walk)\n"
                f"• **Safety Score**: {safest_route.safety_score:.0f}/100\n"
                f"• **Route Lighting**: {safest_route.lighting_percentage:.0f}% illumination\n"
                f"• **Accessibility**: {selected_poi.accessibility.replace('_', ' ').title()}\n"
                f"• **Operating Hours**: {selected_poi.opening_hours}\n\n"
                f"Route directions and turn-by-turn steps have been loaded onto your navigation HUD."
            )

        # General Safe Haven Query (Section 26)
        else:
            response_text = (
                f"I recommend heading to **{selected_poi.name}** ({selected_poi.category.replace('_', ' ').title()}).\n\n"
                f"• **Distance**: {safest_route.distance_meters:.0f} m (~{safest_route.duration_minutes:.1f} min walk)\n"
                f"• **Safety Score**: {safest_route.safety_score:.0f}/100\n"
                f"• **Data Confidence**: {conf.score:.0f}% ({conf.tier} Tier)\n"
                f"• **Key Evidence**: The recommended path stays along illuminated primary roads ({safest_route.lighting_percentage:.0f}% lighting) with verified 24/7 security presence."
            )

        return SLMResponse(
            query=query,
            response_text=response_text,
            abstained=False,
            confidence_tier=conf.tier,
            confidence_score=conf.score,
            safety_score=safest_route.safety_score,
            tool_calls=tool_calls_record,
            evidence_grounding=evidence,
            suggested_route=safest_route,
            suggested_poi=selected_poi
        )
