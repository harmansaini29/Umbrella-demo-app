"""
Project UMBRELLA: Client SDK Core
Manages communication between target microservices and the UMBRELLA Mission Control.
"""

import os
import sys
import time
import json
import logging
import threading
import traceback
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger("umbrella_sdk")


class UmbrellaConfig:
    """Configuration schema for UMBRELLA Agentic Client."""

    def __init__(
        self,
        mission_control_url: str = "http://localhost:8000",
        api_key: str = "umb_live_k8s_9921fx",
        service_name: str = "demo_booking_service",
        repo_path: Optional[str] = None,
        config_file: str = "config.py",
        auto_heal_enabled: bool = True,
        telemetry_interval_sec: float = 2.0,
        metrics_collector: Optional[Callable[[], Dict[str, Any]]] = None
    ):
        self.mission_control_url = mission_control_url.rstrip("/")
        self.api_key = api_key
        self.service_name = service_name
        self.repo_path = repo_path or os.getcwd()
        self.config_file = config_file
        self.auto_heal_enabled = auto_heal_enabled
        self.telemetry_interval_sec = telemetry_interval_sec
        self.metrics_collector = metrics_collector

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mission_control_url": self.mission_control_url,
            "api_key": self.api_key,
            "service_name": self.service_name,
            "repo_path": self.repo_path,
            "config_file": self.config_file,
            "auto_heal_enabled": self.auto_heal_enabled,
            "telemetry_interval_sec": self.telemetry_interval_sec
        }


class UmbrellaClient:
    """
    Primary connector embedded within external client microservices.
    Enables automatic fault interception, live telemetry streaming, and closed-loop healing.
    """

    def __init__(self, config: Optional[UmbrellaConfig] = None):
        self.config = config or UmbrellaConfig()
        self._running = False
        self._telemetry_thread: Optional[threading.Thread] = None
        self._registered = False

    def _post(self, path: str, payload: Dict[str, Any], timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """Utility for non-blocking HTTP POST without heavy third-party requirements."""
        url = f"{self.config.mission_control_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "X-Umbrella-API-Key": self.config.api_key,
                "User-Agent": f"UmbrellaSDK/{self.config.service_name}"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status in (200, 201):
                    body = response.read().decode("utf-8")
                    return json.loads(body)
        except Exception as e:
            logger.debug(f"[UMBRELLA SDK] Request to {url} failed: {e}")
            return None
        return None

    def register(self) -> bool:
        """Registers this service instance with UMBRELLA Mission Control."""
        payload = {
            "service_name": self.config.service_name,
            "repo_path": self.config.repo_path,
            "config_file": self.config.config_file,
            "auto_heal_enabled": self.config.auto_heal_enabled,
            "registered_at": time.time(),
            "pid": os.getpid()
        }
        res = self._post("/api/sdk/register", payload)
        if res and res.get("status") == "registered":
            self._registered = True
            logger.info(f"[UMBRELLA SDK] Successfully registered '{self.config.service_name}' with Mission Control.")
            return True
        return False

    def send_telemetry(self, telemetry_data: Dict[str, Any]) -> bool:
        """Dispatches live operational telemetry snapshot to Mission Control."""
        payload = {
            "service_name": self.config.service_name,
            "timestamp": time.time(),
            "data": telemetry_data
        }
        res = self._post("/api/sdk/telemetry", payload)
        return res is not None

    def report_incident(
        self,
        exception: BaseException,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Captures unhandled exceptions and triggers real-time 6-Agent Council healing loop.
        """
        tb = traceback.format_exc()
        exc_type = type(exception).__name__
        exc_msg = str(exception)

        # Parse AST file location from traceback
        tb_frames = traceback.extract_tb(exception.__traceback__) if exception.__traceback__ else []
        target_file = self.config.config_file
        target_line = 1
        if tb_frames:
            last_frame = tb_frames[-1]
            target_file = last_frame.filename
            target_line = last_frame.lineno

        payload = {
            "service_name": self.config.service_name,
            "timestamp": time.time(),
            "error_type": exc_type,
            "error_message": exc_msg,
            "stack_trace": tb,
            "target_file": target_file,
            "target_line": target_line,
            "context": context or {},
            "repo_path": self.config.repo_path
        }

        logger.warning(f"[UMBRELLA SDK] Reporting incident {exc_type}: {exc_msg} to Mission Control...")
        return self._post("/api/sdk/incident", payload, timeout=15.0)

    def start_telemetry_loop(self):
        """Starts a background thread to continuously ship live telemetry."""
        if self._running:
            return
        self._running = True

        def _loop():
            # Initial registration
            self.register()
            while self._running:
                try:
                    metrics = {}
                    if self.config.metrics_collector:
                        metrics = self.config.metrics_collector()
                    self.send_telemetry(metrics)
                except Exception as ex:
                    logger.debug(f"[UMBRELLA SDK] Telemetry poll failed: {ex}")
                time.sleep(self.config.telemetry_interval_sec)

        self._telemetry_thread = threading.Thread(target=_loop, daemon=True, name="umbrella-telemetry-thread")
        self._telemetry_thread.start()

    def stop_telemetry_loop(self):
        """Halts the telemetry background collector."""
        self._running = False
        if self._telemetry_thread:
            self._telemetry_thread.join(timeout=1.0)
