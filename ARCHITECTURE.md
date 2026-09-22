# SafePlace — Technical Architecture & Class Specifications

> **Offline-First AI Safety Copilot**  
> Complete Architectural Reference, Object-Oriented Class Models, Execution Flows, and Responsible AI Guardrails

---

## 1. Object-Oriented UML Class Diagram

SafePlace is engineered using a decoupled, modular object-oriented architecture. Core analytical engines operate independently of the transport layer, utilizing deterministic algorithms and local SQLite spatial indexing.

![SafePlace UML Class Diagram](docs/diagrams/diagram_class_model.png)

```mermaid
classDiagram
    class OfflineDatabase {
        +Path db_path
        +Connection _get_connection()
        +get_all_pois() List~POI~
        +get_poi_by_id(id) POI
        +get_nearby_pois(lat, lon, max_m, cat) List~Tuple~
        +get_all_road_segments() List~RoadSegment~
        +get_incidents_near_point(lat, lon, radius) List~Incident~
        +set_global_data_age_hours(hours)
    }

    class SafetyRiskEngine {
        +OfflineDatabase db
        +Dict weights
        +evaluate_poi_safety(poi, lat, lon, age) SafetyScore
        +evaluate_segment_safety(segment) float
        +get_incident_risk_penalty(lat, lon, radius) float
    }

    class ConfidenceEngine {
        +Dict thresholds
        +Dict weights
        +calculate_data_age_hours(iso_str) float
        +calculate_freshness_score(age_hours) float
        +evaluate_poi_confidence(poi, age_override) ConfidenceScore
        +evaluate_segment_confidence(segment) ConfidenceScore
    }

    class SafeRouteEngine {
        +OfflineDatabase db
        +SafetyRiskEngine risk_engine
        +ConfidenceEngine confidence_engine
        +Graph graph
        +Dict node_coords
        +build_graph()
        +find_nearest_node(lat, lon) str
        +calculate_routes_to_destination(lat, lon, dest, mode, age) Tuple~Route, Route~
        +synthesize_turn_steps(path_nodes) List~RouteStep~
    }

    class SafeBubbleMonitor {
        +OfflineDatabase db
        +SafetyRiskEngine risk_engine
        +ConfidenceEngine confidence_engine
        +calculate_safe_bubble(lat, lon, mode, age) SafeBubbleResult
        +evaluate_band_reachability(time_min, speed) float
        +rank_destinations(candidates) List
    }

    class OnDeviceSLMCopilot {
        +OfflineDatabase db
        +SafetyRiskEngine risk_engine
        +ConfidenceEngine confidence_engine
        +SafeRouteEngine route_engine
        +SafeBubbleMonitor safe_bubble_monitor
        +process_query(query, lat, lon, age, mode) SLMResponse
        +tool_get_safe_bubble(lat, lon, age) Dict
        +tool_find_nearby_pois(lat, lon, cat) List
        +tool_calculate_risk(poi_id, lat, lon) Dict
        +tool_calculate_confidence(poi_id) Dict
        +tool_calculate_safe_route(lat, lon, dest_id) Dict
        +tool_get_incidents(lat, lon, radius) List
    }

    class POI {
        +str id
        +str name
        +str category
        +float lat
        +float lon
        +str opening_hours
        +str accessibility
        +str verification_status
        +float confidence
    }

    class RoadSegment {
        +str id
        +str u_node
        +str v_node
        +float length_meters
        +float lighting
        +bool footpath
        +bool cctv_available
        +float incident_density
    }

    class Route {
        +str id
        +str mode
        +float distance_meters
        +float duration_minutes
        +float safety_score
        +float risk_score
        +float lighting_percentage
        +List~RouteStep~ steps
    }

    class EmergencyPlan {
        +str status
        +POI safest_destination
        +Route safest_route
        +Route fastest_route
        +str slm_guidance
        +bool abstained
    }

    OfflineDatabase <-- SafetyRiskEngine : queries POIs & segments
    OfflineDatabase <-- SafeRouteEngine : builds graph
    OfflineDatabase <-- SafeBubbleMonitor : evaluates havens
    SafetyRiskEngine <-- SafeRouteEngine : edge risk cost
    ConfidenceEngine <-- SafeRouteEngine : edge uncertainty cost
    SafetyRiskEngine <-- SafeBubbleMonitor : ranks haven safety
    ConfidenceEngine <-- SafeBubbleMonitor : audits haven freshness
    SafeRouteEngine <-- OnDeviceSLMCopilot : executes route tools
    SafeBubbleMonitor <-- OnDeviceSLMCopilot : executes bubble tools
    SafeRouteEngine --> Route : returns dual routes
    SafeBubbleMonitor --> POI : evaluates havens
    OnDeviceSLMCopilot --> EmergencyPlan : generates 1-tap plan
```

---

## 2. Complete Architectural Flows Used

SafePlace coordinates several deterministic pipelines depending on user intent and contextual state:

### Flow 1: User Geolocation & Dynamic Spatial Anchoring Flow
```
[User GPS / Preset Selector] 
       │
       ▼
[GET /api/pois or POST /api/set-location]
       │
       ▼
[ensure_location_context(lat, lon)]
       ├─► Nearest POI <= 5000m? ──► Use Existing Local Spatial Network
       │
       └─► Nearest POI > 5000m? ──► [seed_database_with_coords()]
                                           │
                                           ├─► Synthesizes verified local havens (Police, Hospital, 24/7 Pharmacy)
                                           ├─► Generates illuminated road grid & alleyways
                                           └─► [route_engine.build_graph()] (Rebuilds NetworkX routing graph)
```

---

### Flow 2: Dynamic Safe Bubble & Isochrone Reachability Flow
Calculates reachable safe havens across **5-minute, 10-minute, and 15-minute** time windows based on user travel mode:

```
[Safe Bubble Request (lat, lon, mode)]
       │
       ├─► Mode: Walking  ──► Speed = 4.5 km/h  ──► 5m: 375m  | 10m: 750m  | 15m: 1125m
       └─► Mode: Driving  ──► Speed = 30.0 km/h ──► 5m: 2500m | 10m: 5000m | 15m: 7500m
       │
       ▼
[Haversine Geospatial Sweep across all local POIs]
       │
       ▼
[For each candidate POI within 15-min isochrone]:
       ├─► SafetyRiskEngine: Computes Multi-Factor Haven Safety Score (0-100)
       ├─► ConfidenceEngine: Evaluates Freshness Decay & Source Trust
       └─► Classifies into 5m, 10m, or 15m Band
       │
       ▼
[Sort & Select Recommended Haven] ──► Output SafeBubbleResult (Bands, Zone Confidence)
```

---

### Flow 3: Dual Route Pathfinding Flow (Safest vs. Fastest)
SafePlace computes two distinct paths through the local NetworkX graph to highlight the trade-off between well-lit corridors and dark shortcuts:

![Safe Route vs Fastest Route Pathfinding](docs/diagrams/diagram_dual_routing.png)

```
[Start Node (User Origin)] ───────────────► [Target Node (Safe Haven)]
           │                                          │
           ├─► FASTEST ROUTE OBJECTIVE:               │
           │   Edge Weight = Travel Time (s)          │
           │   Algorithm: Dijkstra Shortest Path      │
           │   Result: Minimizes pure duration        │
           │   (Cuts through dark alleyway shortcut)  │
           │                                          │
           └─► SAFEST ROUTE OBJECTIVE:                │
               Edge Weight = Time + Risk + Uncert.    │
               Risk Penalty = (Risk/100) * 2.2 * Time │
               Uncertainty  = (Unc/100)  * 1.5 * Time │
               Algorithm: Weighted A* / Dijkstra      │
               Result: Maximizes illumination (100%), │
               CCTV coverage, and raised footpaths    │
```

---

### Flow 4: Emergency Mode ("I'M NOT SAFE") Flow
1-tap instantaneous distress flow executing with zero external network dependency:

![Emergency Mode Execution Sequence](docs/diagrams/diagram_emergency_sequence.png)

```
[User Taps 'I'M NOT SAFE']
       │
       ▼
[POST /api/emergency (user_lat, user_lon, travel_mode)]
       │
       ├─► 1. Trigger SafeBubble: Finds all havens within 15-min reachability
       ├─► 2. Rank Havens: Selects highest-safety 24/7 haven (Police / Trauma Hospital)
       ├─► 3. Route Engine: Generates illuminated escape corridor + baseline fastest route
       ├─► 4. Confidence Check: Verifies data freshness (warns if stale)
       └─► 5. Synthesizes Emergency Guidance Action Plan
       │
       ▼
[Client HUD Response]:
       ├─► Flashes high-visibility Red Emergency Banner
       ├─► Triggers oscillating Emergency Audio Siren
       ├─► Draws bold Green Escape Corridor on Map
       └─► Native SpeechSynthesis reads aloud turn-by-turn spoken guidance
```

---

### Flow 5: On-Device SLM Tool Calling & "I Don't Know" Abstention Guardrail
The on-device SLM Copilot (LiteRT-LM / Gemma compact) utilizes a strictly controlled tool-use pipeline to prevent hallucination:

![On-Device SLM Copilot and Guardrails](docs/diagrams/diagram_slm_copilot.png)

```
[User Natural Query: "Is this route safe?"]
       │
       ▼
[Semantic Intent Router]
       │
       ├─► Invokes: tool_calculate_risk(poi_id)
       ├─► Invokes: tool_calculate_confidence(poi_id)
       └─► Invokes: tool_calculate_safe_route(lat, lon, dest_id)
       │
       ▼
[Data Trust & Confidence Audit]:
       │
       ├─► Confidence >= 40.0%?
       │   └──► GROUNDED RECOMMENDATION:
       │        • Recommends verified haven with 24/7 status
       │        • Explains route evidence: 100% lighting, CCTV, footpaths
       │        • Provides concrete walk time and distance
       │
       └─► Confidence < 40.0%? (Stale data > 14 days / 720h)
           └──► EXPLICIT ABSTENTION ("I Don't Know" Guardrail):
                • Refuses to guess or provide false safety guarantees
                • "I don't have enough recent information to make a recommendation."
                • Advises dialing 112 or proceeding cautiously along major illuminated roads.
```

---

## 3. Mathematical Scoring Formulations

### 3.1 Multi-Factor Safety Risk Model (0–100)
$$\text{Safety Score} = 0.25 \cdot I + 0.20 \cdot E + 0.15 \cdot A + 0.15 \cdot (100 - P) + 0.10 \cdot L + 0.10 \cdot F + 0.05 \cdot D$$

* $I$ (**Infrastructure**, 25%): Primary thoroughfare (100) vs. secondary road (75) vs. narrow alleyway (30).
* $E$ (**Emergency Proximity**, 20%): Direct emergency facility presence (100) or decaying with distance: $\max(20, 100 - d/20)$.
* $A$ (**Activity Proxy**, 15%): 24/7 verified commercial hubs, transit terminals, high foot traffic (95) vs. isolated (75).
* $P$ (**Incident Pattern**, 15%): Density penalty calculated from aggregated safety reports within 400m radius.
* $L$ (**Street Lighting**, 10%): Illumination factor ($0.0 - 1.0 \times 100$).
* $F$ (**Pedestrian Footpath**, 10%): Dedicated separated pedestrian walkway present ($100$ if true, $0$ if false).
* $D$ (**Data Freshness**, 5%): Freshness decay score ($0 - 100$).

### 3.2 Exponential Freshness Half-Life Decay
$$\text{Freshness}(t) = 100 \times \exp\left(-0.693 \times \frac{t - 6.0}{96.0}\right) \quad (\text{for } t > 6\text{ hours})$$

* Data under 6 hours old maintains **100% freshness**.
* Half-life $t_{1/2} = 96\text{ hours}$ (4 days).
* After 336 hours (14 days), freshness drops below 10%, lowering composite confidence below $40\%$ and triggering the **"I Don't Know" abstention mechanism**.
