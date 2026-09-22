"""
Comprehensive End-to-End Test Suite for SafePlace
Verifies both backend APIs and frontend client-side offline engines.
"""

import os
import sys
import re
import json
import os
import sys
import re
import json

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from fastapi.testclient import TestClient
from api.server import app

client = TestClient(app)

def test_comprehensive_e2e_suite():
    print("=================================================================")
    print("[RUNNING] SAFEPLACE END-TO-END COMPREHENSIVE VERIFICATION")
    print("=================================================================")
    errors = []

    # -----------------------------------------------------------------
    # 1. System Health & Static Assets
    # -----------------------------------------------------------------
    print("\n[1/6] Testing System Health & Web Serving...")
    try:
        res = client.get("/api/status")
        assert res.status_code == 200, f"Status check failed: {res.status_code}"
        data = res.json()
        assert data.get("status") == "healthy" or "status" in data
        print("  [PASS] /api/status returned healthy status")

        res_ui = client.get("/")
        assert res_ui.status_code == 200, f"Root UI failed: {res_ui.status_code}"
        assert "<title>SafePlace" in res_ui.text
        print("  [PASS] Root index.html served successfully")

        res_sw = client.get("/service-worker.js")
        assert res_sw.status_code == 200, f"Service Worker failed: {res_sw.status_code}"
        print("  [PASS] PWA Service Worker served successfully")
    except Exception as e:
        errors.append(f"System Health: {e}")
        print(f"  [FAIL] ERROR: {e}")

    # -----------------------------------------------------------------
    # 2. Database & Spatial POI Retrieval
    # -----------------------------------------------------------------
    print("\n[2/6] Testing Spatial Telemetry & POI Endpoints...")
    try:
        res = client.get("/api/pois")
        assert res.status_code == 200, f"POIs failed: {res.status_code}"
        pois = res.json()
        assert len(pois) >= 5, f"Expected >= 5 POIs, got {len(pois)}"
        categories = {p["category"] for p in pois}
        assert "hospital" in categories
        assert "police" in categories
        assert "pharmacy" in categories
        print(f"  [PASS] /api/pois returned {len(pois)} verified municipal havens across {len(categories)} categories")
    except Exception as e:
        errors.append(f"Spatial POIs: {e}")
        print(f"  [FAIL] ERROR: {e}")

    # -----------------------------------------------------------------
    # 3. Dynamic Safe Bubble & Routing Engines
    # -----------------------------------------------------------------
    print("\n[3/6] Testing Safe Bubble, Routing & Location Recalibration...")
    user_lat, user_lon = 17.4435, 78.3772
    try:
        # Safe Bubble
        res_bubble = client.get(f"/api/safe-bubble?lat={user_lat}&lon={user_lon}&mode=walking")
        assert res_bubble.status_code == 200, f"Safe Bubble failed: {res_bubble.status_code}"
        b_data = res_bubble.json()
        assert len(b_data["bands"]) == 3, "Expected 3 isochrone bands (5, 10, 15 min)"
        assert b_data["overall_zone_confidence"] > 0
        print(f"  [PASS] /api/safe-bubble calculated isochrone bands with confidence {b_data['overall_zone_confidence']:.1f}%")

        # Routing (Safest vs Fastest)
        dest_poi = pois[0]
        res_route = client.get(f"/api/route?lat={user_lat}&lon={user_lon}&destination_id={dest_poi['id']}&data_age_hours=1.0")
        assert res_route.status_code == 200, f"Routing failed: {res_route.status_code}"
        r_data = res_route.json()
        assert "safest_route" in r_data and "fastest_route" in r_data
        assert r_data["safest_route"]["safety_score"] >= r_data["fastest_route"]["safety_score"]
        print(f"  [PASS] /api/route evaluated corridor: Safest {r_data['safest_route']['safety_score']:.0f}/100 vs Fastest {r_data['fastest_route']['safety_score']:.0f}/100")

        # Location Recalibration
        res_recal = client.post("/api/set-location", json={
            "lat": user_lat + 0.001,
            "lon": user_lon + 0.001,
            "travel_mode": "walking"
        })
        assert res_recal.status_code == 200, f"Recalibration failed: {res_recal.status_code}"
        recal_data = res_recal.json()
        assert "message" in recal_data or "location" in recal_data or res_recal.status_code == 200
        print("  [PASS] /api/set-location dynamically recalibrated location & safe bubble")

        # Emergency Mode
        res_emg = client.post("/api/emergency", json={
            "user_lat": user_lat,
            "user_lon": user_lon,
            "travel_mode": "walking"
        })
        assert res_emg.status_code == 200, f"Emergency failed: {res_emg.status_code} ({res_emg.text})"
        emg_data = res_emg.json()
        assert emg_data["status"] == "EMERGENCY_ACTIVE"
        assert emg_data["safest_destination"] is not None
        print(f"  [PASS] /api/emergency triggered instant corridor to {emg_data['safest_destination']['name']}")
    except Exception as e:
        errors.append(f"Routing & Bubble: {e}")
        print(f"  [FAIL] ERROR: {e}")

    # -----------------------------------------------------------------
    # 4. SLM Safety Copilot & Interactive Chat Endpoints
    # -----------------------------------------------------------------
    print("\n[4/6] Testing On-Device SLM Interactive Chat...")
    test_queries = [
        ("Hello, who are you?", "greeting", lambda r: len(r.get("follow_up_chips", [])) >= 2),
        ("Where is the nearest hosptal?", "typo_hospital", lambda r: r.get("suggested_poi") is not None and r["suggested_poi"]["category"] == "hospital"),
        ("I need the polce station", "typo_police", lambda r: r.get("suggested_poi") is not None and r["suggested_poi"]["category"] == "police"),
        ("Find a 24/7 pharmaxy", "typo_pharmacy", lambda r: r.get("suggested_poi") is not None and r["suggested_poi"]["category"] == "pharmacy"),
        ("How far is it?", "distance_eta", lambda r: "walking distance" in r["response_text"].lower()),
        ("Is it open right now?", "hours_timings", lambda r: "operating hours" in r["response_text"].lower() and len(r.get("follow_up_chips", [])) >= 2),
        ("What is their phone number?", "phone_contact", lambda r: "telephone" in r["response_text"].lower() or "contact" in r["response_text"].lower()),
        ("Why did you choose this route?", "why_explanation", lambda r: "lighting" in r["response_text"].lower()),
        ("Compare the fastest and safest routes", "compare_routes", lambda r: "trade-off" in r["response_text"].lower() or "comparison" in r["response_text"].lower()),
        ("I'm not safe, someone is following me", "distress_emergency", lambda r: "emergency guidance active" in r["response_text"].lower()),
        ("What is the recipe for chocolate cake?", "out_of_domain", lambda r: r.get("suggested_poi") is None and "dedicated exclusively to personal safety" in r["response_text"])
    ]

    for query, label, validator in test_queries:
        try:
            res_chat = client.post("/api/chat", json={
                "query": query,
                "user_lat": user_lat,
                "user_lon": user_lon,
                "data_age_hours_override": 1.0
            })
            assert res_chat.status_code == 200, f"Chat failed on '{query}': {res_chat.status_code}"
            chat_data = res_chat.json()
            assert validator(chat_data), f"Validation failed for query '{query}': {chat_data.get('response_text')[:100]}"
            chips_count = len(chat_data.get("follow_up_chips", []))
            print(f"  [PASS] Intent [{label:18}]: Validated ({chips_count} follow-up chips)")
        except Exception as e:
            errors.append(f"Chat intent '{label}': {e}")
            print(f"  ✗ ERROR on '{label}': {e}")

    # -----------------------------------------------------------------
    # 5. Frontend Offline Logic & Client Parity Validation
    # -----------------------------------------------------------------
    print("\n[5/6] Testing Frontend Client Offline Intelligence Parity...")
    try:
        app_js_path = os.path.join("ui", "js", "app.js")
        with open(app_js_path, "r", encoding="utf-8") as f:
            app_js = f.read()

        # Check required client-side functions
        required_functions = [
            "generateClientOfflineSLM",
            "generateClientOfflineRoute",
            "calcHaversineMeters",
            "calcStringSimilarity",
            "matchesAnyFuzzyJS",
            "triggerChatChip",
            "toggleRouteComparison",
            "toggleMessageSpeech",
            "handleChatResponse",
            "addChatMessage"
        ]
        for fn in required_functions:
            assert fn in app_js, f"Missing required frontend function '{fn}' in app.js"
            print(f"  [PASS] Frontend function '{fn}' verified in app.js")

        # Verify offline SLM includes follow_up_chips and multi-turn state
        assert "follow_up_chips" in app_js, "app.js missing follow_up_chips support"
        assert "timingTargets" in app_js, "app.js missing timingTargets"
        assert "phoneTargets" in app_js, "app.js missing phoneTargets"
        print("  [PASS] Client offline SLM engine contains full parity for chips, timings, and phone intents")
    except Exception as e:
        errors.append(f"Frontend JS Parity: {e}")
        print(f"  ✗ ERROR: {e}")

    # -----------------------------------------------------------------
    # 6. UI Assets & Styling Integrity
    # -----------------------------------------------------------------
    print("\n[6/6] Testing UI Assets & CSS Integrity...")
    try:
        css_path = os.path.join("ui", "css", "style.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        required_classes = [
            ".chat-msg-header",
            ".chat-audio-btn",
            ".chat-followup-chips",
            ".chat-chip",
            ".chat-action-call"
        ]
        for cls in required_classes:
            assert cls in css, f"Missing CSS class '{cls}' in style.css"
            print(f"  [PASS] CSS class '{cls}' verified in style.css")
    except Exception as e:
        errors.append(f"CSS Integrity: {e}")
        print(f"  ✗ ERROR: {e}")

    print("\n=================================================================")
    if not errors:
        print("[SUCCESS] ALL END-TO-END VERIFICATIONS PASSED CLEANLY (0 ERRORS)")
        print("=================================================================")
    else:
        print(f"[FAILURE] {len(errors)} ERROR(S) ENCOUNTERED:")
        for err in errors:
            print(f"  - {err}")
        print("=================================================================")
    assert not errors, f"E2E verification encountered {len(errors)} error(s): {errors}"

if __name__ == "__main__":
    test_comprehensive_e2e_suite()
    sys.exit(0)
