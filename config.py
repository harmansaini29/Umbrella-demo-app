"""
Umbrella Demo App (Karamstay PG Rental Service): Configuration
Models initial constrained database capacity to predictably demonstrate concurrency bottlenecks
under multi-tenant checkout traffic, auto-healing with Project UMBRELLA.
"""

import os

# Database settings
DATABASE_URL = os.environ.get("DEMO_DATABASE_URL", "sqlite:///./karamstay_demo.sqlite")

# Initially constrained pool settings to predictably demonstrate bottleneck under 10 concurrent users
POOL_SIZE = int(os.environ.get("DEMO_POOL_SIZE", "2"))
MAX_OVERFLOW = int(os.environ.get("DEMO_MAX_OVERFLOW", "0"))
POOL_TIMEOUT = float(os.environ.get("DEMO_POOL_TIMEOUT", "1.0"))
SERVICE_PORT = int(os.environ.get("DEMO_SERVICE_PORT", "8002"))

# Project UMBRELLA Integration Settings
UMBRELLA_MISSION_CONTROL_URL = os.environ.get("UMBRELLA_MISSION_CONTROL_URL", "http://localhost:8000")
UMBRELLA_API_KEY = os.environ.get("UMBRELLA_API_KEY", "umb_live_k8s_9921fx")
UMBRELLA_AGENT_ENABLED = os.environ.get("UMBRELLA_AGENT_ENABLED", "true").lower() in ("true", "1", "yes")
