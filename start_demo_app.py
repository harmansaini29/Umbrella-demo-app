"""
Umbrella Demo App Runner: Launches the Karamstay PG Rental Microservice
"""

import sys
import uvicorn
import config

if __name__ == "__main__":
    host = os.environ.get("DEMO_HOST", "127.0.0.1")
    print("=" * 80)
    print("STARTING UMBRELLA DEMO APP (KARAMSTAY PG RENTAL SERVICE)")
    print(f"👉 OPEN IN BROWSER: http://localhost:{config.SERVICE_PORT} or http://127.0.0.1:{config.SERVICE_PORT}")
    print("   (Note: Do NOT enter 0.0.0.0 in browser address bar)")
    print(f"Connected UMBRELLA Mission Control: {config.UMBRELLA_MISSION_CONTROL_URL}")
    print("=" * 80)
    uvicorn.run("server:app", host=host, port=config.SERVICE_PORT, reload=False)
