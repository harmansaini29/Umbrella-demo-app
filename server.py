"""
Umbrella Demo App (Karamstay PG Room Rental & Payment Service)
FastAPI microservice modeling a high-traffic PG rental platform.
Includes live interactive Chaos Injection controls (10 simultaneous payments, 100 concurrent users at 1 RPS),
and connects autonomously to Project UMBRELLA Mission Control via the UMBRELLA Agentic Client SDK.
"""

import os
import sys
import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, HTTPException, status, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import config
from database import get_db, init_db, engine, SessionLocal
from models import Room, Booking, RentPayment
from load_simulator import run_10_simultaneous_payments, run_100_concurrent_tenants_1rps
from umbrella_sdk import UmbrellaClient, UmbrellaConfig, UmbrellaFastAPIMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("karamstay_demo_app")

app = FastAPI(
    title="Umbrella Demo App: Karamstay PG Rental Service",
    description="Live target microservice connected to Project UMBRELLA for autonomous incident detection & self-healing.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Recent live activity log buffer for UI
live_event_log: List[Dict[str, Any]] = []


def log_event(event_type: str, message: str, status_code: int = 200, details: Optional[Dict[str, Any]] = None):
    entry = {
        "id": str(uuid.uuid4())[:8],
        "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3],
        "type": event_type,
        "message": message,
        "status_code": status_code,
        "details": details or {}
    }
    live_event_log.insert(0, entry)
    if len(live_event_log) > 100:
        live_event_log.pop()


# Setup UMBRELLA Client SDK Integration
def collect_telemetry() -> Dict[str, Any]:
    """Collects real-time pool metrics for UMBRELLA Mission Control."""
    checkedout = engine.pool.checkedout() if engine and hasattr(engine, "pool") else 0
    size = engine.pool.size() if engine and hasattr(engine, "pool") else config.POOL_SIZE
    return {
        "service_name": "karamstay_demo_app",
        "pool_size": size,
        "checked_out_connections": checkedout,
        "overflow": engine.pool.overflow() if engine and hasattr(engine, "pool") else 0,
        "utilization_pct": round((checkedout / max(size, 1)) * 100.0, 1),
        "database_url": config.DATABASE_URL,
        "repo_path": os.path.abspath(os.path.dirname(__file__))
    }


umbrella_config = UmbrellaConfig(
    mission_control_url=config.UMBRELLA_MISSION_CONTROL_URL,
    api_key=config.UMBRELLA_API_KEY,
    service_name="karamstay_demo_app",
    repo_path=os.path.abspath(os.path.dirname(__file__)),
    config_file=os.path.abspath(os.path.join(os.path.dirname(__file__), "config.py")),
    auto_heal_enabled=config.UMBRELLA_AGENT_ENABLED,
    metrics_collector=collect_telemetry
)

umbrella_client = UmbrellaClient(config=umbrella_config)

if config.UMBRELLA_AGENT_ENABLED:
    app.add_middleware(UmbrellaFastAPIMiddleware, client=umbrella_client)
    # Start background telemetry reporting
    umbrella_client.start_telemetry_loop()
    logger.info("[UMBRELLA] Embedded SDK active. Shipping telemetry to " + config.UMBRELLA_MISSION_CONTROL_URL)


class BookingRequest(BaseModel):
    tenant_name: str = Field(..., example="Aarav Sharma")
    phone: str = Field(default="+91 98765 43210")
    room_number: str = Field(default="ROOM-101")
    bed_number: str = Field(default="Bed-A")


class PaymentRequest(BaseModel):
    booking_id: int = Field(default=1)
    tenant_name: str = Field(..., example="Aarav Sharma")
    amount: float = Field(default=8500.0)
    payment_method: str = Field(default="UPI / Razorpay")


@app.get("/")
def get_web_ui():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Umbrella Demo App UI ready at /static/index.html"}


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "karamstay_demo_app",
        "pool_size": config.POOL_SIZE,
        "max_overflow": config.MAX_OVERFLOW,
        "pool_timeout": config.POOL_TIMEOUT,
        "umbrella_agent_connected": config.UMBRELLA_AGENT_ENABLED
    }


@app.get("/metrics")
def metrics():
    checkedout = engine.pool.checkedout() if engine and hasattr(engine, "pool") else 0
    size = engine.pool.size() if engine and hasattr(engine, "pool") else config.POOL_SIZE
    return {
        "pool_size": size,
        "checked_out_connections": checkedout,
        "overflow": engine.pool.overflow() if engine and hasattr(engine, "pool") else 0,
        "utilization_pct": round((checkedout / max(size, 1)) * 100.0, 1),
        "umbrella_agent_connected": config.UMBRELLA_AGENT_ENABLED
    }


@app.get("/rooms")
def list_rooms(db: Session = Depends(get_db)):
    rooms = db.query(Room).all()
    return [
        {
            "id": r.id,
            "room_number": r.room_number,
            "room_type": r.room_type,
            "rent": r.monthly_rent,
            "floor": r.floor,
            "amenities": r.amenities,
            "available": r.is_available
        }
        for r in rooms
    ]


@app.post("/book-room", status_code=status.HTTP_201_CREATED)
def book_room(req: BookingRequest, db: Session = Depends(get_db)):
    # Hold connection for realistic DB lock
    time.sleep(0.20)
    room = db.query(Room).filter(Room.room_number == req.room_number).first()
    if not room:
        room = db.query(Room).first()

    booking = Booking(
        tenant_name=req.tenant_name,
        phone=req.phone,
        room_id=room.id if room else 1,
        bed_number=req.bed_number,
        status="confirmed"
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    log_event("BOOKING_CREATED", f"Room {req.room_number} booked by {req.tenant_name}", 201)
    return {
        "booking_id": booking.id,
        "tenant_name": booking.tenant_name,
        "room_number": req.room_number,
        "bed_number": booking.bed_number,
        "status": booking.status,
        "created_at": booking.created_at.isoformat()
    }


@app.post("/pay-rent", status_code=status.HTTP_201_CREATED)
def pay_rent(req: PaymentRequest, db: Session = Depends(get_db)):
    # Force checkout of a raw connection and simulate payment gateway lock
    conn = db.connection()
    time.sleep(1.40)  # 1.4s payment lock > 1.0s pool timeout

    payment = RentPayment(
        booking_id=req.booking_id,
        tenant_name=req.tenant_name,
        amount=req.amount,
        payment_method=req.payment_method,
        status="completed",
        transaction_ref=f"TXN-KARAM-{uuid.uuid4().hex[:8].upper()}",
        invoice_id=f"INV-{int(time.time())}"
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    log_event("RENT_PAID", f"Rent ₹{req.amount} processed for {req.tenant_name} ({payment.transaction_ref})", 201)
    return {
        "payment_id": payment.id,
        "tenant_name": payment.tenant_name,
        "amount": payment.amount,
        "transaction_ref": payment.transaction_ref,
        "invoice_id": payment.invoice_id,
        "status": payment.status
    }


@app.post("/api/chaos/10-payments")
def trigger_10_simultaneous_payments():
    """Chaos Engine Button 1: 10 Simultaneous Rent Payments."""
    log_event("CHAOS_TRIGGERED", "Firing 10 Simultaneous Tenant Rent Payments (1.4s gateway lock)", 200)
    summary = run_10_simultaneous_payments()

    if summary["failed_requests"] > 0:
        log_event(
            "BACKEND_CRASH",
            f"QueuePool Exhaustion: {summary['failed_requests']}/10 requests crashed (500 Error)",
            500,
            details=summary
        )
        # Notify UMBRELLA via SDK directly
        if config.UMBRELLA_AGENT_ENABLED:
            exc = TimeoutError(f"sqlalchemy.exc.TimeoutError: {summary['first_error_msg']}")
            umbrella_client.report_incident(exc, context={"scenario": "10_payments", "summary": summary})
    else:
        log_event("CHAOS_COMPLETED", "All 10 simultaneous payments succeeded! Capacity sufficient.", 200)

    return summary


@app.post("/api/chaos/100-users-1rps")
def trigger_100_users_load():
    """Chaos Engine Button 2: 100 Concurrent Tenants Load at 1 RPS."""
    log_event("CHAOS_TRIGGERED", "Firing 100 Concurrent Tenants Traffic Wave at 1 RPS", 200)
    summary = run_100_concurrent_tenants_1rps()

    if summary["failed_requests"] > 0:
        log_event(
            "BACKEND_CRASH",
            f"Overload Starvation: {summary['failed_requests']}/100 requests failed (500 Error)",
            500,
            details=summary
        )
        if config.UMBRELLA_AGENT_ENABLED:
            exc = TimeoutError(f"sqlalchemy.exc.TimeoutError: {summary['first_error_msg']}")
            umbrella_client.report_incident(exc, context={"scenario": "100_users_1rps", "summary": summary})
    else:
        log_event("CHAOS_COMPLETED", "All 100 concurrent requests succeeded with 0 errors!", 200)

    return summary


@app.get("/api/events")
def get_recent_events():
    """Returns recent activity and failure logs for the live UI."""
    return {"events": live_event_log[:50]}


@app.post("/api/config/reload")
def reload_config():
    """Dynamically reloads config.py after UMBRELLA patch application."""
    init_db()
    log_event("CONFIG_RELOADED", f"Capacity reloaded: POOL_SIZE={config.POOL_SIZE}, MAX_OVERFLOW={config.MAX_OVERFLOW}", 200)
    return {
        "status": "reloaded",
        "pool_size": config.POOL_SIZE,
        "max_overflow": config.MAX_OVERFLOW,
        "pool_timeout": config.POOL_TIMEOUT
    }


@app.post("/reset")
def reset_demo_state():
    """Resets the demo backend to baseline constrained parameters (POOL_SIZE=2)."""
    cfg_file = os.path.join(os.path.dirname(__file__), "config.py")
    if os.path.exists(cfg_file):
        with open(cfg_file, "r", encoding="utf-8") as f:
            c = f.read()
        c = c.replace('POOL_SIZE = int(os.environ.get("DEMO_POOL_SIZE", "20"))', 'POOL_SIZE = int(os.environ.get("DEMO_POOL_SIZE", "2"))')
        c = c.replace('POOL_SIZE = int(os.environ.get("DEMO_POOL_SIZE", "10"))', 'POOL_SIZE = int(os.environ.get("DEMO_POOL_SIZE", "2"))')
        c = c.replace('POOL_SIZE = 20', 'POOL_SIZE = 2')
        c = c.replace('POOL_SIZE = 10', 'POOL_SIZE = 2')
        c = c.replace('MAX_OVERFLOW = 10', 'MAX_OVERFLOW = 0')
        c = c.replace('MAX_OVERFLOW = 5', 'MAX_OVERFLOW = 0')
        with open(cfg_file, "w", encoding="utf-8") as f:
            f.write(c)

    init_db()
    log_event("RESET_EXECUTED", "Demo database and pool reset to constrained state (POOL_SIZE=2)", 200)
    return {"message": "Reset to baseline (POOL_SIZE=2, MAX_OVERFLOW=0)."}


if __name__ == "__main__":
    import uvicorn
    print("=" * 80)
    print("UMBRELLA DEMO APP: KARAMSTAY PG RENTAL SERVICE LAUNCHING")
    print(f"Port: {config.SERVICE_PORT} | Access UI at: http://localhost:{config.SERVICE_PORT}")
    print(f"UMBRELLA Protection: {config.UMBRELLA_AGENT_ENABLED} ({config.UMBRELLA_MISSION_CONTROL_URL})")
    print("=" * 80)
    uvicorn.run(app, host="0.0.0.0", port=config.SERVICE_PORT)
