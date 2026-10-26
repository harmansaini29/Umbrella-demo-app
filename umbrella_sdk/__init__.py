"""
Project UMBRELLA: Enterprise Client Integration SDK
Empowers external applications with autonomous self-healing, real-time telemetry streaming,
and AST fault reporting to Project UMBRELLA Mission Control.
"""

from umbrella_sdk.client import UmbrellaClient, UmbrellaConfig
from umbrella_sdk.middleware import UmbrellaFastAPIMiddleware

__version__ = "2.0.0"
__all__ = ["UmbrellaClient", "UmbrellaConfig", "UmbrellaFastAPIMiddleware"]
