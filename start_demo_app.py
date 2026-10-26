"""
Umbrella Demo App Runner: Launches the Karamstay PG Rental Microservice
"""

import sys
import uvicorn
import config

if __name__ == "__main__":
    print("=" * 80)
    print("STARTING UMBRELLA DEMO APP (KARAMSTAY PG RENTAL SERVICE)")
    print(f"Server Port: {config.SERVICE_PORT}")
    print(f"Open Browser: http://localhost:{config.SERVICE_PORT}")
    print(f"Connected UMBRELLA Mission Control: {config.UMBRELLA_MISSION_CONTROL_URL}")
    print("=" * 80)
    uvicorn.run("server:app", host="0.0.0.0", port=config.SERVICE_PORT, reload=False)
