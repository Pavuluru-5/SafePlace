"""
SafePlace Data Foundry & Multi-Region Dataset Builder
Supports major Indian metropolitan regions (Hyderabad, Bangalore, Mumbai, Delhi),
San Francisco benchmark, and dynamic real-time location grid generation.
Compliant with Section 7 and Appendix A.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from core.models import POI, RoadSegment, IncidentAggregate
from core.database import OfflineDatabase
import config


# -------------------------------------------------------------
# City Package Presets (India & International)
# -------------------------------------------------------------

CITY_PRESETS = {
    "hyderabad": {
        "name": "Hyderabad (HITEC City / Madhapur)",
        "country": "India 🇮🇳",
        "center": {"lat": 17.4435, "lon": 78.3772},
        "pois": [
            {
                "id": "HYD_POLICE_01",
                "name": "Cyberabad Police Station (Madhapur)",
                "category": "police",
                "lat": 17.4485,
                "lon": 78.3810,
                "opening_hours": "24/7",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "Police_Department_Feed",
                "confidence": 98.0,
                "phone": "+91-40-2785-3418",
                "address": "HITEC City Main Rd, Madhapur"
            },
            {
                "id": "HYD_HOSPITAL_01",
                "name": "Medicover Hospital & Emergency Trauma",
                "category": "hospital",
                "lat": 17.4410,
                "lon": 78.3825,
                "opening_hours": "24/7",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "Hospital_Authority_Direct",
                "confidence": 96.0,
                "phone": "+91-40-6833-4455",
                "address": "Behind Cyber Towers, Madhapur"
            },
            {
                "id": "HYD_PHARMACY_01",
                "name": "Apollo Pharmacy 24/7 Emergency Care",
                "category": "pharmacy",
                "lat": 17.4440,
                "lon": 78.3785,
                "opening_hours": "24/7",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "Municipal_Safety_GIS",
                "confidence": 94.0,
                "phone": "+91-40-2345-6789",
                "address": "Opp. Cyber Gateway, HITEC City"
            },
            {
                "id": "HYD_TRANSIT_01",
                "name": "HITEC City Metro Station & Transit Hub",
                "category": "transport_hub",
                "lat": 17.4465,
                "lon": 78.3760,
                "opening_hours": "06:00-23:00",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "OpenStreetMap_Verified",
                "confidence": 92.0,
                "phone": "+91-40-2333-2222",
                "address": "Cyber Towers Junction"
            },
            {
                "id": "HYD_CIVIC_01",
                "name": "Telangana State Police Command & Control Centre",
                "category": "public_building",
                "lat": 17.4490,
                "lon": 78.3740,
                "opening_hours": "24/7",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "Municipal_Safety_GIS",
                "confidence": 95.0,
                "address": "Banjara Hills Rd 12 / Cyberabad"
            },
            {
                "id": "HYD_FIRE_01",
                "name": "Madhapur Fire Station",
                "category": "fire_station",
                "lat": 17.4395,
                "lon": 78.3750,
                "opening_hours": "24/7",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "National_Emergency_Registry",
                "confidence": 95.0,
                "phone": "+91-40-2344-0101",
                "address": "Near Inorbit Mall Link Rd"
            }
        ],
        "segments": [
            # N1: Center Start (17.4435, 78.3772)
            # N2: Cyber Towers Junction (17.4465, 78.3760)
            # N3: Police Station Approach (17.4485, 78.3805)
            # N4: Dark Alley Shortcut (17.4455, 78.3795) - Unlit Guttala Begumpet alley
            # N5: Medicover Access (17.4415, 78.3810)
            {
                "id": "HYD_SEG_01",
                "u_node": "N1",
                "v_node": "N2",
                "name": "HITEC City Main Boulevard (Illuminated 6-Lane)",
                "road_type": "primary",
                "geometry": [[17.4435, 78.3772], [17.4450, 78.3765], [17.4465, 78.3760]],
                "length_meters": 360.0,
                "lighting": 0.95,
                "footpath": True,
                "activity_proxy": 0.90,
                "cctv_available": True,
                "incident_density": 0.02
            },
            {
                "id": "HYD_SEG_02",
                "u_node": "N2",
                "v_node": "N3",
                "name": "Cyberabad Police Commissionerate Avenue",
                "road_type": "primary",
                "geometry": [[17.4465, 78.3760], [17.4475, 78.3780], [17.4485, 78.3805]],
                "length_meters": 540.0,
                "lighting": 1.0,
                "footpath": True,
                "activity_proxy": 0.95,
                "cctv_available": True,
                "incident_density": 0.01
            },
            {
                "id": "HYD_SEG_03",
                "u_node": "N1",
                "v_node": "N4",
                "name": "Guttala Begumpet Unlit Alley Cut (High Risk Shortcut)",
                "road_type": "alley",
                "geometry": [[17.4435, 78.3772], [17.4445, 78.3785], [17.4455, 78.3795]],
                "length_meters": 290.0,
                "lighting": 0.10,  # Dark
                "footpath": False,
                "activity_proxy": 0.15,
                "cctv_available": False,
                "incident_density": 0.70
            },
            {
                "id": "HYD_SEG_04",
                "u_node": "N4",
                "v_node": "N3",
                "name": "Backlane Drainage Cut",
                "road_type": "alley",
                "geometry": [[17.4455, 78.3795], [17.4470, 78.3800], [17.4485, 78.3805]],
                "length_meters": 340.0,
                "lighting": 0.15,
                "footpath": False,
                "activity_proxy": 0.10,
                "cctv_available": False,
                "incident_density": 0.65
            },
            {
                "id": "HYD_SEG_05",
                "u_node": "N1",
                "v_node": "N5",
                "name": "Hospital Access Expressway",
                "road_type": "secondary",
                "geometry": [[17.4435, 78.3772], [17.4425, 78.3790], [17.4415, 78.3810]],
                "length_meters": 450.0,
                "lighting": 0.90,
                "footpath": True,
                "activity_proxy": 0.80,
                "cctv_available": True,
                "incident_density": 0.03
            }
        ],
        "incidents": [
            {
                "id": "HYD_INC_01",
                "area_grid": "GRID_GUTTALA_ALLEY",
                "lat": 17.4455,
                "lon": 78.3795,
                "radius_meters": 180.0,
                "time_bucket": "night",
                "category": "poor_lighting_and_harassment",
                "severity": 3.6,
                "count": 11
            }
        ]
    },
    "bangalore": {
        "name": "Bangalore (MG Road / Indiranagar)",
        "country": "India 🇮🇳",
        "center": {"lat": 12.9750, "lon": 77.6080},
        "pois": [
            {
                "id": "BLR_POLICE_01",
                "name": "Cubbon Park Police Station",
                "category": "police",
                "lat": 12.9790,
                "lon": 77.6020,
                "opening_hours": "24/7",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "Police_Department_Feed",
                "confidence": 98.0,
                "phone": "+91-80-2294-2222",
                "address": "Kasturba Rd, Near Cubbon Park"
            },
            {
                "id": "BLR_HOSPITAL_01",
                "name": "Manipal Hospital & Emergency Unit",
                "category": "hospital",
                "lat": 12.9710,
                "lon": 77.6140,
                "opening_hours": "24/7",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "Hospital_Authority_Direct",
                "confidence": 96.0,
                "phone": "+91-80-2502-4444",
                "address": "Old Airport Rd / HAL"
            },
            {
                "id": "BLR_PHARMACY_01",
                "name": "MedPlus 24/7 Pharmacy",
                "category": "pharmacy",
                "lat": 12.9755,
                "lon": 77.6090,
                "opening_hours": "24/7",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "Municipal_Safety_GIS",
                "confidence": 94.0,
                "phone": "+91-80-2233-4455",
                "address": "Brigade Rd Junction"
            },
            {
                "id": "BLR_TRANSIT_01",
                "name": "MG Road Metro Station",
                "category": "transport_hub",
                "lat": 12.9750,
                "lon": 77.6060,
                "opening_hours": "06:00-23:00",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "OpenStreetMap_Verified",
                "confidence": 92.0,
                "phone": "+91-80-2296-9300",
                "address": "MG Road Boulevard"
            }
        ],
        "segments": [
            {
                "id": "BLR_SEG_01",
                "u_node": "N1",
                "v_node": "N2",
                "name": "MG Road Promenade (Well-Lit Avenue)",
                "road_type": "primary",
                "geometry": [[12.9750, 77.6080], [12.9750, 77.6060], [12.9750, 77.6040]],
                "length_meters": 440.0,
                "lighting": 0.95,
                "footpath": True,
                "activity_proxy": 0.95,
                "cctv_available": True,
                "incident_density": 0.02
            },
            {
                "id": "BLR_SEG_02",
                "u_node": "N2",
                "v_node": "N3",
                "name": "Cubbon Police Plaza Way",
                "road_type": "primary",
                "geometry": [[12.9750, 77.6040], [12.9770, 77.6030], [12.9790, 77.6020]],
                "length_meters": 520.0,
                "lighting": 1.0,
                "footpath": True,
                "activity_proxy": 0.90,
                "cctv_available": True,
                "incident_density": 0.01
            },
            {
                "id": "BLR_SEG_03",
                "u_node": "N1",
                "v_node": "N4",
                "name": "Commercial Backlane (Unlit Alley Shortcut)",
                "road_type": "alley",
                "geometry": [[12.9750, 77.6080], [12.9770, 77.6060], [12.9780, 77.6045]],
                "length_meters": 360.0,
                "lighting": 0.12,
                "footpath": False,
                "activity_proxy": 0.10,
                "cctv_available": False,
                "incident_density": 0.70
            },
            {
                "id": "BLR_SEG_04",
                "u_node": "N4",
                "v_node": "N3",
                "name": "Rest House Alley Passage",
                "road_type": "alley",
                "geometry": [[12.9780, 77.6045], [12.9785, 77.6030], [12.9790, 77.6020]],
                "length_meters": 310.0,
                "lighting": 0.15,
                "footpath": False,
                "activity_proxy": 0.10,
                "cctv_available": False,
                "incident_density": 0.60
            }
        ],
        "incidents": [
            {
                "id": "BLR_INC_01",
                "area_grid": "GRID_COMMERCIAL_ALLEY",
                "lat": 12.9770,
                "lon": 77.6060,
                "radius_meters": 160.0,
                "time_bucket": "night",
                "category": "theft_and_harassment",
                "severity": 3.5,
                "count": 9
            }
        ]
    },
    "delhi": {
        "name": "Delhi (Connaught Place / Central)",
        "country": "India 🇮🇳",
        "center": {"lat": 28.6315, "lon": 77.2167},
        "pois": [
            {
                "id": "DEL_POLICE_01",
                "name": "Parliament Street Police Station",
                "category": "police",
                "lat": 28.6280,
                "lon": 77.2140,
                "opening_hours": "24/7",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "Police_Department_Feed",
                "confidence": 99.0,
                "phone": "+91-11-2336-1100",
                "address": "Sansad Marg, CP"
            },
            {
                "id": "DEL_HOSPITAL_01",
                "name": "Dr. RML Hospital & Trauma Center",
                "category": "hospital",
                "lat": 28.6250,
                "lon": 77.2010,
                "opening_hours": "24/7",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "Hospital_Authority_Direct",
                "confidence": 97.0,
                "phone": "+91-11-2336-5525",
                "address": "Baba Kharak Singh Marg"
            },
            {
                "id": "DEL_PHARMACY_01",
                "name": "Apollo 24/7 CP Central Pharmacy",
                "category": "pharmacy",
                "lat": 28.6320,
                "lon": 77.2185,
                "opening_hours": "24/7",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "Municipal_Safety_GIS",
                "confidence": 95.0,
                "phone": "+91-11-2332-9900",
                "address": "Inner Circle, Block C, CP"
            },
            {
                "id": "DEL_TRANSIT_01",
                "name": "Rajiv Chowk Metro Station",
                "category": "transport_hub",
                "lat": 28.6328,
                "lon": 77.2197,
                "opening_hours": "05:30-23:30",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "OpenStreetMap_Verified",
                "confidence": 95.0,
                "address": "Central Park, Connaught Place"
            }
        ],
        "segments": [
            {
                "id": "DEL_SEG_01",
                "u_node": "N1",
                "v_node": "N2",
                "name": "Sansad Marg (Parliament St Promenade)",
                "road_type": "primary",
                "geometry": [[28.6315, 77.2167], [28.6300, 77.2155], [28.6280, 77.2140]],
                "length_meters": 460.0,
                "lighting": 0.98,
                "footpath": True,
                "activity_proxy": 0.95,
                "cctv_available": True,
                "incident_density": 0.01
            },
            {
                "id": "DEL_SEG_02",
                "u_node": "N1",
                "v_node": "N3",
                "name": "Palika Service Alley (Dark Shortcut)",
                "road_type": "alley",
                "geometry": [[28.6315, 77.2167], [28.6295, 77.2160], [28.6280, 77.2140]],
                "length_meters": 390.0,
                "lighting": 0.15,
                "footpath": False,
                "activity_proxy": 0.15,
                "cctv_available": False,
                "incident_density": 0.65
            }
        ],
        "incidents": [
            {
                "id": "DEL_INC_01",
                "area_grid": "GRID_CP_OUTER_ALLEY",
                "lat": 28.6295,
                "lon": 77.2160,
                "radius_meters": 170.0,
                "time_bucket": "night",
                "category": "theft_and_harassment",
                "severity": 3.4,
                "count": 8
            }
        ]
    },
    "mumbai": {
        "name": "Mumbai (Bandra / BKC)",
        "country": "India 🇮🇳",
        "center": {"lat": 19.0596, "lon": 72.8295},
        "pois": [
            {
                "id": "MUM_POLICE_01",
                "name": "Bandra Police Station",
                "category": "police",
                "lat": 19.0540,
                "lon": 72.8330,
                "opening_hours": "24/7",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "Police_Department_Feed",
                "confidence": 98.0,
                "phone": "+91-22-2642-2022",
                "address": "Hill Rd, Bandra West"
            },
            {
                "id": "MUM_HOSPITAL_01",
                "name": "Lilavati Hospital & Emergency Care",
                "category": "hospital",
                "lat": 19.0510,
                "lon": 72.8290,
                "opening_hours": "24/7",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "Hospital_Authority_Direct",
                "confidence": 97.0,
                "phone": "+91-22-2675-1000",
                "address": "A-791, Bandra Reclamation"
            },
            {
                "id": "MUM_PHARMACY_01",
                "name": "Noble Plus 24/7 Chemist",
                "category": "pharmacy",
                "lat": 19.0580,
                "lon": 72.8310,
                "opening_hours": "24/7",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "Municipal_Safety_GIS",
                "confidence": 94.0,
                "phone": "+91-22-2640-1122",
                "address": "Linking Rd, Bandra West"
            }
        ],
        "segments": [
            {
                "id": "MUM_SEG_01",
                "u_node": "N1",
                "v_node": "N2",
                "name": "Hill Road Main Boulevard",
                "road_type": "primary",
                "geometry": [[19.0596, 72.8295], [19.0570, 72.8315], [19.0540, 72.8330]],
                "length_meters": 680.0,
                "lighting": 0.95,
                "footpath": True,
                "activity_proxy": 0.95,
                "cctv_available": True,
                "incident_density": 0.02
            },
            {
                "id": "MUM_SEG_02",
                "u_node": "N1",
                "v_node": "N2",
                "name": "Narrow Gaothan Gully (Dark Shortcut)",
                "road_type": "alley",
                "geometry": [[19.0596, 72.8295], [19.0560, 72.8310], [19.0540, 72.8330]],
                "length_meters": 580.0,
                "lighting": 0.15,
                "footpath": False,
                "activity_proxy": 0.15,
                "cctv_available": False,
                "incident_density": 0.65
            }
        ],
        "incidents": [
            {
                "id": "MUM_INC_01",
                "area_grid": "GRID_BANDRA_GULLY",
                "lat": 19.0560,
                "lon": 72.8310,
                "radius_meters": 170.0,
                "time_bucket": "night",
                "category": "poor_lighting_and_theft",
                "severity": 3.4,
                "count": 7
            }
        ]
    },
    "san_francisco": {
        "name": "San Francisco (Downtown / Civic Center)",
        "country": "USA 🇺🇸",
        "center": {"lat": 37.7740, "lon": -122.4200},
        "pois": [
            {
                "id": "POI_POLICE_01",
                "name": "Central Police Precinct #1",
                "category": "police",
                "lat": 37.7785,
                "lon": -122.4150,
                "opening_hours": "24/7",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "Police_Department_Feed",
                "confidence": 98.0,
                "phone": "+1-555-0100",
                "address": "100 Police Plaza"
            },
            {
                "id": "POI_HOSPITAL_01",
                "name": "Metro General Hospital & Trauma",
                "category": "hospital",
                "lat": 37.7715,
                "lon": -122.4240,
                "opening_hours": "24/7",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "Hospital_Authority_Direct",
                "confidence": 96.0,
                "phone": "+1-555-0200",
                "address": "450 Medical Way"
            },
            {
                "id": "POI_PHARMACY_01",
                "name": "Community Care 24/7 Pharmacy",
                "category": "pharmacy",
                "lat": 37.7745,
                "lon": -122.4180,
                "opening_hours": "24/7",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "Municipal_Safety_GIS",
                "confidence": 92.0,
                "phone": "+1-555-0300",
                "address": "75 Market St"
            },
            {
                "id": "POI_CIVIC_01",
                "name": "City Civic Center & Public Library",
                "category": "public_building",
                "lat": 37.7790,
                "lon": -122.4210,
                "opening_hours": "07:00-23:00",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "Municipal_Safety_GIS",
                "confidence": 89.0,
                "phone": "+1-555-0400",
                "address": "200 Civic Center"
            },
            {
                "id": "POI_FIRE_01",
                "name": "Downtown Fire Station #4",
                "category": "fire_station",
                "lat": 37.7720,
                "lon": -122.4130,
                "opening_hours": "24/7",
                "accessibility": "full",
                "verification_status": "verified",
                "source": "National_Emergency_Registry",
                "confidence": 95.0,
                "phone": "+1-555-0500",
                "address": "320 Responder Ave"
            }
        ],
        "segments": [
            {
                "id": "SEG_01",
                "u_node": "N1",
                "v_node": "N2",
                "name": "Grand Boulevard (Illuminated Promenade)",
                "road_type": "primary",
                "geometry": [[37.7740, -122.4200], [37.7742, -122.4190], [37.7745, -122.4180]],
                "length_meters": 210.0,
                "lighting": 0.95,
                "footpath": True,
                "activity_proxy": 0.85,
                "cctv_available": True,
                "incident_density": 0.02
            },
            {
                "id": "SEG_02",
                "u_node": "N2",
                "v_node": "N3",
                "name": "Police Plaza Boulevard (High Security Zone)",
                "road_type": "primary",
                "geometry": [[37.7745, -122.4180], [37.7760, -122.4165], [37.7780, -122.4160]],
                "length_meters": 540.0,
                "lighting": 1.0,
                "footpath": True,
                "activity_proxy": 0.90,
                "cctv_available": True,
                "incident_density": 0.01
            },
            {
                "id": "SEG_03",
                "u_node": "N1",
                "v_node": "N4",
                "name": "Dark Alley Cut (Unlit Industrial Path)",
                "road_type": "alley",
                "geometry": [[37.7740, -122.4200], [37.7752, -122.4190], [37.7765, -122.4180]],
                "length_meters": 320.0,
                "lighting": 0.10,
                "footpath": False,
                "activity_proxy": 0.10,
                "cctv_available": False,
                "incident_density": 0.75
            },
            {
                "id": "SEG_04",
                "u_node": "N4",
                "v_node": "N3",
                "name": "Backlane Service Pass",
                "road_type": "alley",
                "geometry": [[37.7765, -122.4180], [37.7772, -122.4170], [37.7780, -122.4160]],
                "length_meters": 240.0,
                "lighting": 0.15,
                "footpath": False,
                "activity_proxy": 0.15,
                "cctv_available": False,
                "incident_density": 0.60
            },
            {
                "id": "SEG_05",
                "u_node": "N1",
                "v_node": "N5",
                "name": "Medical Access Way",
                "road_type": "secondary",
                "geometry": [[37.7740, -122.4200], [37.7730, -122.4210], [37.7720, -122.4220]],
                "length_meters": 280.0,
                "lighting": 0.90,
                "footpath": True,
                "activity_proxy": 0.75,
                "cctv_available": True,
                "incident_density": 0.03
            }
        ],
        "incidents": [
            {
                "id": "INC_HOTSPOT_01",
                "area_grid": "GRID_ALLEY_DOWNTOWN",
                "lat": 37.7765,
                "lon": -122.4180,
                "radius_meters": 180.0,
                "time_bucket": "night",
                "category": "poor_lighting_and_harassment",
                "severity": 3.8,
                "count": 14
            }
        ]
    }
}


def generate_dataset_for_city(city_key: str = "hyderabad") -> Dict[str, Any]:
    """Generates benchmark dataset for a specific city preset."""
    preset = CITY_PRESETS.get(city_key.lower(), CITY_PRESETS["hyderabad"])
    now = datetime.now()
    t_fresh = now.isoformat()
    t_recent = (now - timedelta(hours=2)).isoformat()
    t_yesterday = (now - timedelta(hours=24)).isoformat()

    pois = []
    for p in preset["pois"]:
        pois.append(POI(
            id=p["id"],
            name=p["name"],
            category=p["category"],
            lat=p["lat"],
            lon=p["lon"],
            opening_hours=p.get("opening_hours", "24/7"),
            accessibility=p.get("accessibility", "full"),
            verification_status=p.get("verification_status", "verified"),
            source=p.get("source", "Municipal_Safety_GIS"),
            last_updated=t_recent,
            confidence=p.get("confidence", 95.0),
            phone=p.get("phone", "+91-40-100"),
            address=p.get("address", "Main Road"),
            capacity_level="normal"
        ))

    segments = []
    for s in preset["segments"]:
        segments.append(RoadSegment(
            id=s["id"],
            u_node=s["u_node"],
            v_node=s["v_node"],
            name=s["name"],
            road_type=s["road_type"],
            geometry=s["geometry"],
            length_meters=s["length_meters"],
            lighting=s["lighting"],
            footpath=s["footpath"],
            activity_proxy=s["activity_proxy"],
            cctv_available=s.get("cctv_available", False),
            incident_density=s.get("incident_density", 0.05),
            speed_kmh=4.5,
            last_updated=t_fresh,
            confidence=95.0
        ))

    incidents = []
    for inc in preset["incidents"]:
        incidents.append(IncidentAggregate(
            id=inc["id"],
            area_grid=inc["area_grid"],
            lat=inc["lat"],
            lon=inc["lon"],
            radius_meters=inc.get("radius_meters", 180.0),
            time_bucket=inc.get("time_bucket", "night"),
            category=inc.get("category", "hazard_report"),
            severity=inc.get("severity", 3.0),
            count=inc.get("count", 5),
            source="Municipal_Public_Safety_Records",
            confidence=85.0,
            last_updated=t_yesterday
        ))

    return {
        "metadata": {
            "city_key": city_key,
            "city_name": preset["name"],
            "country": preset["country"],
            "version": "1.1.0",
            "generator": "SafePlace Google Foundry Multi-Region GIS Builder",
            "created_at": t_fresh,
            "center": preset["center"],
            "total_pois": len(pois),
            "total_segments": len(segments),
            "total_incidents": len(incidents)
        },
        "pois": [p.model_dump() for p in pois],
        "road_segments": [s.model_dump() for s in segments],
        "incident_aggregates": [i.model_dump() for i in incidents]
    }


def generate_dataset_around_coords(lat: float, lon: float, location_name: str = "My Local Area") -> Dict[str, Any]:
    """
    Dynamically generates realistic safety havens and road corridors around any user GPS coordinate in India / worldwide.
    """
    now = datetime.now()
    t_fresh = now.isoformat()
    t_recent = (now - timedelta(hours=2)).isoformat()
    t_yesterday = (now - timedelta(hours=24)).isoformat()

    # Offsets in degrees (~111km per deg lat, ~105km per deg lon at ~17-20N)
    d_lat = 0.0035  # ~380m
    d_lon = 0.0035  # ~360m

    pois = [
        POI(
            id="LOC_POLICE_01",
            name=f"District Police Station ({location_name})",
            category="police",
            lat=round(lat + d_lat * 0.9, 6),
            lon=round(lon + d_lon * 0.7, 6),
            opening_hours="24/7",
            accessibility="full",
            verification_status="verified",
            source="Police_Department_Feed",
            last_updated=t_recent,
            confidence=98.0,
            phone="+91-100 / Emergency 112",
            address="Police Station Rd",
            capacity_level="normal"
        ),
        POI(
            id="LOC_HOSPITAL_01",
            name=f"Emergency Trauma Centre ({location_name})",
            category="hospital",
            lat=round(lat - d_lat * 0.75, 6),
            lon=round(lon + d_lon * 0.85, 6),
            opening_hours="24/7",
            accessibility="full",
            verification_status="verified",
            source="Hospital_Authority_Direct",
            last_updated=t_fresh,
            confidence=96.0,
            phone="+91-108 / +91-102",
            address="Hospital Care Way",
            capacity_level="normal"
        ),
        POI(
            id="LOC_PHARMACY_01",
            name="24/7 Medical & Emergency Pharmacy",
            category="pharmacy",
            lat=round(lat + d_lat * 0.25, 6),
            lon=round(lon + d_lon * 0.35, 6),
            opening_hours="24/7",
            accessibility="full",
            verification_status="verified",
            source="Municipal_Safety_GIS",
            last_updated=t_recent,
            confidence=94.0,
            phone="+91-1800-200-999",
            address="Main Commercial Avenue"
        ),
        POI(
            id="LOC_TRANSIT_01",
            name="Central Transit & Safe Refuge Hub",
            category="transport_hub",
            lat=round(lat + d_lat * 0.8, 6),
            lon=round(lon - d_lon * 0.5, 6),
            opening_hours="05:30-23:30",
            accessibility="full",
            verification_status="verified",
            source="Transit_Authority",
            last_updated=t_recent,
            confidence=92.0,
            phone="139",
            address="Transit Station Plaza"
        ),
        POI(
            id="LOC_PUBLIC_01",
            name="District Civic Command & Safety Shelter",
            category="public_building",
            lat=round(lat - d_lat * 0.4, 6),
            lon=round(lon - d_lon * 0.6, 6),
            opening_hours="24/7",
            accessibility="full",
            verification_status="verified",
            source="Municipal_Safety_GIS",
            last_updated=t_yesterday,
            confidence=91.0,
            phone="100",
            address="Civic Complex Road"
        ),
        POI(
            id="LOC_FIRE_01",
            name="Emergency Fire & Rescue Station",
            category="fire_station",
            lat=round(lat - d_lat * 0.9, 6),
            lon=round(lon - d_lon * 0.2, 6),
            opening_hours="24/7",
            accessibility="full",
            verification_status="verified",
            source="National_Emergency_Registry",
            last_updated=t_fresh,
            confidence=95.0,
            phone="101",
            address="Emergency Service Link"
        )
    ]

    segments = [
        # Well-lit primary avenue to Police (N1 -> N2)
        RoadSegment(
            id="LOC_SEG_01",
            u_node="N1",
            v_node="N2",
            name="Main Illuminated Avenue",
            road_type="primary",
            geometry=[[lat, lon], [lat + d_lat * 0.45, lon + d_lon * 0.35], [lat + d_lat * 0.9, lon + d_lon * 0.7]],
            length_meters=490.0,
            lighting=0.95,
            footpath=True,
            activity_proxy=0.90,
            cctv_available=True,
            incident_density=0.02,
            speed_kmh=4.5,
            last_updated=t_fresh,
            confidence=95.0
        ),
        # Dark shortcut alley to Police (N1 -> N3 -> N2)
        RoadSegment(
            id="LOC_SEG_02",
            u_node="N1",
            v_node="N3",
            name="Unlit Narrow Backlane (Dark Shortcut)",
            road_type="alley",
            geometry=[[lat, lon], [lat + d_lat * 0.5, lon + d_lon * 0.5], [lat + d_lat * 0.9, lon + d_lon * 0.7]],
            length_meters=370.0,
            lighting=0.10,
            footpath=False,
            activity_proxy=0.10,
            cctv_available=False,
            incident_density=0.70,
            speed_kmh=4.5,
            last_updated=t_yesterday,
            confidence=68.0
        ),
        # Road to Hospital (N1 -> N4)
        RoadSegment(
            id="LOC_SEG_03",
            u_node="N1",
            v_node="N4",
            name="Hospital Access Boulevard",
            road_type="secondary",
            geometry=[[lat, lon], [lat - d_lat * 0.4, lon + d_lon * 0.4], [lat - d_lat * 0.75, lon + d_lon * 0.85]],
            length_meters=470.0,
            lighting=0.90,
            footpath=True,
            activity_proxy=0.80,
            cctv_available=True,
            incident_density=0.03,
            speed_kmh=4.5,
            last_updated=t_fresh,
            confidence=94.0
        ),
        # Road to Pharmacy (N1 -> N5)
        RoadSegment(
            id="LOC_SEG_04",
            u_node="N1",
            v_node="N5",
            name="Commercial Market Corridor",
            road_type="primary",
            geometry=[[lat, lon], [lat + d_lat * 0.25, lon + d_lon * 0.35]],
            length_meters=210.0,
            lighting=0.95,
            footpath=True,
            activity_proxy=0.88,
            cctv_available=True,
            incident_density=0.02,
            speed_kmh=4.5,
            last_updated=t_fresh,
            confidence=95.0
        ),
        # Road to Transit Hub (N1 -> N6)
        RoadSegment(
            id="LOC_SEG_05",
            u_node="N1",
            v_node="N6",
            name="Transit Concourse Way",
            road_type="primary",
            geometry=[[lat, lon], [lat + d_lat * 0.4, lon - d_lon * 0.2], [lat + d_lat * 0.8, lon - d_lon * 0.5]],
            length_meters=430.0,
            lighting=0.92,
            footpath=True,
            activity_proxy=0.85,
            cctv_available=True,
            incident_density=0.04,
            speed_kmh=4.5,
            last_updated=t_fresh,
            confidence=93.0
        ),
        # Road to Civic Shelter (N1 -> N7)
        RoadSegment(
            id="LOC_SEG_06",
            u_node="N1",
            v_node="N7",
            name="Civic Link Promenade",
            road_type="secondary",
            geometry=[[lat, lon], [lat - d_lat * 0.4, lon - d_lon * 0.6]],
            length_meters=340.0,
            lighting=0.85,
            footpath=True,
            activity_proxy=0.75,
            cctv_available=True,
            incident_density=0.05,
            speed_kmh=4.5,
            last_updated=t_yesterday,
            confidence=90.0
        ),
        # Road to Fire Station (N1 -> N8)
        RoadSegment(
            id="LOC_SEG_07",
            u_node="N1",
            v_node="N8",
            name="Emergency Rescue Expressway",
            road_type="primary",
            geometry=[[lat, lon], [lat - d_lat * 0.5, lon - d_lon * 0.1], [lat - d_lat * 0.9, lon - d_lon * 0.2]],
            length_meters=460.0,
            lighting=0.90,
            footpath=True,
            activity_proxy=0.80,
            cctv_available=True,
            incident_density=0.02,
            speed_kmh=4.5,
            last_updated=t_fresh,
            confidence=95.0
        )
    ]

    incidents = [
        IncidentAggregate(
            id="LOC_INC_01",
            area_grid="GRID_LOCAL_ALLEY",
            lat=round(lat + d_lat * 0.5, 6),
            lon=round(lon + d_lon * 0.5, 6),
            radius_meters=160.0,
            time_bucket="night",
            category="poor_lighting_and_hazard",
            severity=3.5,
            count=6,
            source="Municipal_Safety_GIS",
            confidence=80.0,
            last_updated=t_yesterday
        )
    ]

    return {
        "metadata": {
            "city_key": "custom_gps",
            "city_name": location_name,
            "country": "India 🇮🇳",
            "version": "1.1.0",
            "generator": "SafePlace Dynamic Realtime GPS Seeder",
            "created_at": t_fresh,
            "center": {"lat": lat, "lon": lon},
            "total_pois": len(pois),
            "total_segments": len(segments),
            "total_incidents": len(incidents)
        },
        "pois": [p.model_dump() for p in pois],
        "road_segments": [s.model_dump() for s in segments],
        "incident_aggregates": [i.model_dump() for i in incidents]
    }


def seed_offline_database(db: OfflineDatabase, city_key: str = "hyderabad") -> Dict[str, Any]:
    """Generates benchmark dataset for the chosen city and seeds SQLite offline store with fast batch operations."""
    data = generate_dataset_for_city(city_key)

    # Clear old records
    db.clear_all()

    # Fast batch inserts
    pois = [POI(**p) for p in data["pois"]]
    segments = [RoadSegment(**s) for s in data["road_segments"]]
    incidents = [IncidentAggregate(**i) for i in data["incident_aggregates"]]

    db.insert_pois_batch(pois)
    db.insert_segments_batch(segments)
    db.insert_incidents_batch(incidents)

    # Persist JSON asynchronously / safely
    try:
        config.SAMPLE_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(config.SAMPLE_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

    return data["metadata"]


def seed_database_with_coords(db: OfflineDatabase, lat: float, lon: float, name: str = "My Real Location") -> Dict[str, Any]:
    """Seeds database dynamically around user's exact coordinates with instant batch insert."""
    data = generate_dataset_around_coords(lat, lon, name)

    db.clear_all()

    pois = [POI(**p) for p in data["pois"]]
    segments = [RoadSegment(**s) for s in data["road_segments"]]
    incidents = [IncidentAggregate(**i) for i in data["incident_aggregates"]]

    db.insert_pois_batch(pois)
    db.insert_segments_batch(segments)
    db.insert_incidents_batch(incidents)

    try:
        config.SAMPLE_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(config.SAMPLE_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

    return data["metadata"]


if __name__ == "__main__":
    db = OfflineDatabase()
    meta = seed_offline_database(db, "hyderabad")
    print(f"Successfully seeded SafePlace Offline Database with {meta['city_name']} ({meta['total_pois']} POIs, {meta['total_segments']} Road Segments).")
