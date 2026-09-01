"""
SafePlace — Startup Script
Initializes database, starts FastAPI server, and launches interactive Web UI.
"""

import sys
import webbrowser
import threading
import time
import uvicorn
from core.database import OfflineDatabase
from data.dataset_builder import seed_offline_database
import config


def open_browser():
    """Wait for server startup and open browser."""
    time.sleep(1.5)
    display_host = "127.0.0.1" if config.SERVER_HOST in ["0.0.0.0", ""] else config.SERVER_HOST
    url = f"http://{display_host}:{config.SERVER_PORT}"
    print(f"\n[SafePlace] Opening UI in web browser: {url}")
    webbrowser.open(url)


def main():
    print("=" * 65)
    print("  🛡️  SafePlace — Offline AI Safety Copilot (Patchamama 2026)")
    print("=" * 65)
    print("  • Mode: OFFLINE-FIRST LOCAL INTELLIGENCE")
    print("  • AI Engine: On-Device LiteRT-LM Gemma Copilot")
    print("  • Spatial Database: SQLite Local GIS Store")
    print("  • Responsible AI: Dynamic Data Trust & Abstention Active")
    print("=" * 65)

    # Initialize local offline database
    db = OfflineDatabase()
    pois = db.get_all_pois()
    if len(pois) == 0:
        print("\n[SafePlace] Seeding benchmark GIS dataset (Default: Hyderabad, India)...")
        seed_offline_database(db, "hyderabad")
        print("[SafePlace] Database successfully seeded.")
    else:
        print(f"\n[SafePlace] Local spatial database loaded ({len(pois)} POIs verified).")

    # Start browser opener in background thread
    threading.Thread(target=open_browser, daemon=True).start()

    print(f"\n[SafePlace] Starting server at http://{config.SERVER_HOST}:{config.SERVER_PORT}")
    print("[SafePlace] Press Ctrl+C to stop.\n")

    uvicorn.run(
        "api.server:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        log_level="info",
        reload=False
    )


if __name__ == "__main__":
    main()
