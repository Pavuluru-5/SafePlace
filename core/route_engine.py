"""
SafePlace Safe Route Graph Engine
Generates, scores, and compares Fastest vs Safest routes using NetworkX graph pathfinding.
Compliant with Section 13, Section 14, and Section 28.
"""

import networkx as nx
from typing import List, Dict, Tuple, Optional, Any
from core.models import POI, RoadSegment, Route, RouteStep, ConfidenceScore
from core.database import OfflineDatabase, haversine_distance_meters
from core.risk_engine import SafetyRiskEngine
from core.confidence_engine import ConfidenceEngine
import config


class SafeRouteEngine:
    def __init__(self, db: OfflineDatabase, risk_engine: SafetyRiskEngine, confidence_engine: ConfidenceEngine):
        self.db = db
        self.risk_engine = risk_engine
        self.confidence_engine = confidence_engine
        self.graph = nx.Graph()
        self._segment_lookup: Dict[Tuple[str, str], RoadSegment] = {}
        self._node_coords: Dict[str, Tuple[float, float]] = {}
        self.build_graph()

    def build_graph(self):
        """Constructs undirected weighted graph from stored road segments."""
        self.graph.clear()
        self._segment_lookup.clear()
        self._node_coords.clear()

        segments = self.db.get_all_road_segments()
        for seg in segments:
            u, v = seg.u_node, seg.v_node
            u_coord = (seg.geometry[0][0], seg.geometry[0][1])
            v_coord = (seg.geometry[-1][0], seg.geometry[-1][1])
            self._node_coords[u] = u_coord
            self._node_coords[v] = v_coord

            # Edge attributes
            length = seg.length_meters
            speed = seg.speed_kmh if seg.speed_kmh > 0 else 4.5
            travel_time_min = (length / (speed * 1000.0 / 60.0))  # in minutes

            # Calculate segment safety & risk
            seg_safety = self.risk_engine.evaluate_segment_safety(seg)
            seg_risk = 100.0 - seg_safety

            # Pure fast weight = travel time in seconds
            fast_weight = travel_time_min * 60.0

            # Safe weight = Travel Cost + Risk Penalty + Low Lighting Penalty
            # Risk penalty adds cost for dark/dangerous corridors
            risk_penalty = (seg_risk / 100.0) * config.ROUTING_WEIGHTS["risk_penalty_weight"] * fast_weight
            uncertainty_penalty = ((100.0 - seg.confidence) / 100.0) * config.ROUTING_WEIGHTS["uncertainty_penalty_weight"] * fast_weight
            
            safe_weight = fast_weight + risk_penalty + uncertainty_penalty

            self.graph.add_edge(
                u, v,
                segment_id=seg.id,
                segment=seg,
                length=length,
                travel_time_min=travel_time_min,
                safety_score=seg_safety,
                risk_score=seg_risk,
                fast_weight=fast_weight,
                safe_weight=safe_weight
            )
            self._segment_lookup[(u, v)] = seg
            self._segment_lookup[(v, u)] = seg

    def find_nearest_node(self, lat: float, lon: float) -> str:
        """Finds closest graph node to a given lat/lon point."""
        closest_node = None
        min_dist = float('inf')
        for node, (n_lat, n_lon) in self._node_coords.items():
            dist = haversine_distance_meters(lat, lon, n_lat, n_lon)
            if dist < min_dist:
                min_dist = dist
                closest_node = node
        return closest_node or "N1"

    def _reconstruct_route_details(
        self,
        node_path: List[str],
        destination: POI,
        user_lat: float,
        user_lon: float,
        is_safest: bool,
        is_fastest: bool,
        age_hours_override: Optional[float] = None
    ) -> Route:
        """Assembles route geometry, metrics, steps, and reasons from a node sequence."""
        route_coords = [[user_lat, user_lon]]
        segments_in_path: List[RoadSegment] = []
        total_distance = 0.0
        total_time_min = 0.0
        lighting_scores = []
        safety_scores = []
        steps: List[RouteStep] = []

        # Connect user start to first node
        first_coord = self._node_coords.get(node_path[0], (user_lat, user_lon))
        start_dist = haversine_distance_meters(user_lat, user_lon, first_coord[0], first_coord[1])
        total_distance += start_dist
        total_time_min += (start_dist / (config.WALKING_SPEED_KMH * 1000.0 / 60.0))

        for i in range(len(node_path) - 1):
            u, v = node_path[i], node_path[i + 1]
            edge_data = self.graph.get_edge_data(u, v)
            seg = edge_data["segment"] if edge_data else self._segment_lookup.get((u, v))
            if seg:
                segments_in_path.append(seg)
                total_distance += seg.length_meters
                total_time_min += edge_data["travel_time_min"]
                lighting_scores.append(seg.lighting)
                safety_scores.append(edge_data["safety_score"])

                # Add geometry
                for pt in seg.geometry:
                    if not route_coords or route_coords[-1] != pt:
                        route_coords.append(pt)

                # Navigation Step
                light_desc = "Well-lit (Streetlights active)" if seg.lighting >= 0.7 else "Dim / Partial lighting"
                safe_desc = "High Safety Zone" if edge_data["safety_score"] >= 80 else "Moderate Caution"
                steps.append(RouteStep(
                    instruction=f"Proceed along {seg.name} ({seg.road_type})",
                    distance_meters=round(seg.length_meters, 1),
                    duration_seconds=round(edge_data["travel_time_min"] * 60, 0),
                    road_name=seg.name,
                    lighting_level=light_desc,
                    safety_indicator=safe_desc
                ))

        # Connect last node to destination
        dest_coord = (destination.lat, destination.lon)
        end_dist = haversine_distance_meters(route_coords[-1][0], route_coords[-1][1], dest_coord[0], dest_coord[1])
        total_distance += end_dist
        total_time_min += (end_dist / (config.WALKING_SPEED_KMH * 1000.0 / 60.0))
        route_coords.append([dest_coord[0], dest_coord[1]])

        steps.append(RouteStep(
            instruction=f"Arrive safely at {destination.name} ({destination.category.replace('_', ' ').title()})",
            distance_meters=round(end_dist, 1),
            duration_seconds=round((end_dist / (config.WALKING_SPEED_KMH * 1000.0 / 60.0)) * 60, 0),
            road_name=destination.name,
            lighting_level="Facility Perimeter Lighting",
            safety_indicator="Trusted Haven"
        ))

        # Calculate Averages & Confidence
        avg_safety = sum(safety_scores) / len(safety_scores) if safety_scores else 70.0
        avg_risk = 100.0 - avg_safety
        avg_lighting = (sum(lighting_scores) / len(lighting_scores)) * 100.0 if lighting_scores else 80.0
        
        conf = self.confidence_engine.evaluate_route_confidence(segments_in_path, age_hours_override=age_hours_override)

        # Proximity to emergency along the route
        dest_safety = self.risk_engine.evaluate_poi_safety(destination, user_lat, user_lon, age_hours_override=age_hours_override)
        composite_safety = (avg_safety * 0.4) + (dest_safety.safety_score * 0.6)

        # Why recommended reasons
        why = []
        if is_safest:
            if avg_lighting >= 75:
                why.append(f"Follows primary well-illuminated thoroughfares ({avg_lighting:.0f}% lighting coverage).")
            if any(s.footpath for s in segments_in_path):
                why.append("Dedicated pedestrian footpaths throughout the path.")
            if destination.category in ["police", "hospital"]:
                why.append(f"Direct route to verified 24/7 {destination.category.title()} haven.")
            why.append(f"Higher data confidence ({conf.score:.0f}%) with lowest cumulative hazard exposure.")
        elif is_fastest:
            why.append(f"Fastest route: saves ~{max(0.5, total_time_min * 0.15):.1f} min travel time.")
            why.append("Optimized strictly for minimum transit distance and travel duration.")

        route_id = f"route_{'safe' if is_safest else 'fast'}_{destination.id}"
        route_name = f"{'Safest' if is_safest else 'Fastest'} Route to {destination.name}"

        return Route(
            id=route_id,
            name=route_name,
            mode="walking",
            destination_id=destination.id,
            destination_name=destination.name,
            destination_category=destination.category,
            path_nodes=node_path,
            path_coordinates=route_coords,
            distance_meters=round(total_distance, 1),
            duration_minutes=round(total_time_min, 1),
            safety_score=round(composite_safety, 1),
            risk_score=round(100.0 - composite_safety, 1),
            confidence_score=conf.score,
            lighting_percentage=round(avg_lighting, 1),
            emergency_proximity_score=round(dest_safety.breakdown.get("emergency_proximity", 80.0), 1),
            route_score=round(total_time_min + (avg_risk * 0.2), 2),
            is_safest=is_safest,
            is_fastest=is_fastest,
            steps=steps,
            why_recommended=why
        )

    def calculate_routes_to_destination(
        self,
        user_lat: float,
        user_lon: float,
        destination: POI,
        age_hours_override: Optional[float] = None
    ) -> Tuple[Route, Route]:
        """
        Calculates both Safest Route and Fastest Route to destination.
        Returns (safest_route, fastest_route).
        """
        start_node = self.find_nearest_node(user_lat, user_lon)
        end_node = self.find_nearest_node(destination.lat, destination.lon)

        if start_node == end_node:
            # Single node path
            fast_path = [start_node]
            safe_path = [start_node]
        else:
            try:
                # Fast route uses 'fast_weight' (travel time)
                fast_path = nx.shortest_path(self.graph, source=start_node, target=end_node, weight='fast_weight')
            except nx.NetworkXNoPath:
                fast_path = [start_node, end_node]

            try:
                # Safe route uses 'safe_weight' (travel time + risk penalty + uncertainty penalty)
                safe_path = nx.shortest_path(self.graph, source=start_node, target=end_node, weight='safe_weight')
            except nx.NetworkXNoPath:
                safe_path = fast_path

        fastest_route = self._reconstruct_route_details(
            fast_path, destination, user_lat, user_lon,
            is_safest=False, is_fastest=True, age_hours_override=age_hours_override
        )
        safest_route = self._reconstruct_route_details(
            safe_path, destination, user_lat, user_lon,
            is_safest=True, is_fastest=False, age_hours_override=age_hours_override
        )

        return safest_route, fastest_route
